# controllers/webhook_menu.py
# -*- coding: utf-8 -*-
from odoo import http
from odoo.http import request
import json
import logging

_logger = logging.getLogger(__name__)

SELLING_TIME_ID = "SELLINGTIME-01"
DAYS = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]

# -----------------------------
# Helpers
# -----------------------------

def _icp_get(key, default=None):
    return request.env['ir.config_parameter'].sudo().get_param(key, default)

def _json_body():
    try:
        data = request.httprequest.data
        if not data:
            return {}
        return json.loads(data.decode('utf-8'))
    except Exception:
        return {}

def _get_param(*names, default=""):
    q = request.httprequest.args
    for n in names:
        v = q.get(n)
        if v:
            return v
    body = _json_body()
    for n in names:
        v = body.get(n)
        if v:
            return v
    return default

def _int_cents(x):
    try:
        return int(round(float(x or 0.0) * 100))
    except Exception:
        return 0

def _normalize_base(u: str) -> str:
    """修正常见手误并去除末尾斜杠，确保是 https://domain"""
    u = (u or '').strip().rstrip('/')
    u = u.replace('https//', 'https://').replace('http//', 'http://')
    if u and '://' not in u:
        u = 'https://' + u
    return u

def _product_image_url(product):
    """
    返回公开可访问的图片 URL：
    1) 优先 product.template.image_1920（为减小体积改用 image_1024）
    2) 回退第一个 product.product.image_1920（同样改用 image_1024）
    3) 再回退外链 URL 字段（系统参数 grab.external_image_field 或常见字段名）
    对 /web/image URL：追加一个“伪文件名” .jpg，并带 unique=xxx 缓存戳，方便第三方正确识别与刷新。
    """
    base = _normalize_base(_icp_get('web.base.url', ''))
    if not base or not product:
        return ""

    def _mk_url(model, rec):
        # Check for any available image field in order of preference
        image_fields = ['image_1920', 'image_1024', 'image_512', 'image_256']
        selected_field = None
        
        for field in image_fields:
            if rec and hasattr(rec, field) and getattr(rec, field, False):
                selected_field = field
                break
        
        if not selected_field:
            return ""
            
        try:
            ts = int(rec.write_date.timestamp()) if rec.write_date else 0
        except Exception:
            ts = 0
        
        # Use the selected image field, with a descriptive filename
        # Example: /web/image/product.template/1784/image_1024/product.jpg?unique=123456
        return f"{base}/web/image/{model}/{rec.id}/{selected_field}/product.jpg?unique={ts}"

    # 1) 模板图
    url = _mk_url('product.template', product)
    if url:
        return url

    # 2) 变体图
    variant = product.product_variant_ids[:1]
    if variant:
        v = variant[0]
        url = _mk_url('product.product', v)
        if url:
            return url

    # 3) 外链 URL 字段兜底
    fname = (_icp_get('grab.external_image_field') or '').strip()
    candidates = [fname] if fname else []
    candidates += ['image_url', 'photo_url', 'website_image_url', 'external_image_url', 'url_image']
    for f in candidates:
        if f and hasattr(product, f):
            val = (getattr(product, f) or "").strip()
            if isinstance(val, str) and val.lower().startswith('http'):
                return val

    return ""

def _price_with_tax(pt):
    """
    返回含税价格（float），用 product.template 的税来计算。
    没税时回退 list_price。
    """
    price = pt.list_price or 0.0
    company = request.env.company
    taxes = pt.taxes_id.filtered(lambda t: t.company_id == company)
    if taxes:
        res = taxes.compute_all(price, currency=pt.currency_id, quantity=1.0, product=pt, partner=None)
        return res.get('total_included', price)
    return price

# ---- status 规范化：统一四个大写枚举 ----
ALLOWED_STATUS = {"AVAILABLE", "UNAVAILABLE", "UNAVAILABLETODAY", "HIDE"}

def _norm_status(val, default="AVAILABLE"):
    """将 availableStatus 统一规范成官方枚举，避免 Menu Simulator 报错。"""
    if val in (None, "", True, False):
        return default
    v = str(val).upper().strip()
    # 常见错误写法容错：空格、下划线、连字符
    v = v.replace(" ", "").replace("_", "").replace("-", "")
    # 只接受四个值
    return v if v in ALLOWED_STATUS else default

def _build_modifier_groups(item):
    """
    构造 Grab 期望的 modifierGroups：
    - selectionRangeMin: 取模型值，默认 0
    - selectionRangeMax:
        * 若模型值 > 0：使用该值（明确的业务上限，例如 2）
        * 若模型值 <= 0 或未填：显式回落为组内 modifier 数量上限（允许选择全部可用）
    - availableStatus：规范成官方四个枚举
    """
    def _as_int(v, default=0):
        try:
            return int(v)
        except Exception:
            return int(default)

    mgs_payload = []
    for mg in item.modifier_group_ids:
        # 1) 读取并规范化 min/max
        sel_min = _as_int(getattr(mg, 'selection_range_min', None), 0)
        raw_max = getattr(mg, 'selection_range_max', None)
        sel_max = _as_int(raw_max, 0)  # 0/None 认为是未指定

        # 2) 未指定/<=0 时，按组内数量上限（显式给出具体整数）
        total_mods = len(mg.modifier_ids)
        if sel_max <= 0:
            sel_max = total_mods

        # 3) 防呆：max 至少要 >= min 且 >=1（与 Grab 前端期望对齐）
        floor = max(sel_min, 1)
        if sel_max < floor:
            sel_max = floor

        # 4) 组装 modifiers（含 availableStatus 规范化）
        modifiers_payload = []
        for m in mg.modifier_ids:
            modifiers_payload.append({
                "id": m.modifier_code or f"MODI-{m.id}",
                "name": m.name,
                "price": int(round((getattr(m, 'price', 0.0) or 0.0) * 100)),
                "availableStatus": _norm_status(getattr(m, 'available_status', None), "AVAILABLE"),
            })

        # 5) 打日志方便核对
        _logger.info(
            "GRAB MG | item=%s mg=%s min=%s max=%s mods=%s",
            (item.display_name or item.name),
            (mg.display_name or mg.name),
            sel_min, sel_max, total_mods
        )

        # 6) 产出 payload（group 状态也规范）
        mgs_payload.append({
            "id": mg.group_code or f"MG-{mg.id}",
            "name": mg.name,
            "selectionRangeMin": sel_min,
            "selectionRangeMax": sel_max,
            "availableStatus": _norm_status(getattr(mg, 'available_status', None), "AVAILABLE"),
            "modifiers": modifiers_payload,
        })

    return mgs_payload

def _build_categories_from_db(menu):
    """把现有 section → category → item 扁平成 selling-time-based categories；"""
    categories = []
    seen_cat = set()
    for section in menu.section_ids:
        for cat in section.category_ids:
            cat_id = f"CATEGORY-{cat.id}"
            if cat_id in seen_cat:
                continue
            seen_cat.add(cat_id)

            items = []
            seen_item = set()
            for it in cat.item_ids:
                it_id = f"ITEM-{it.id}"
                if it_id in seen_item:
                    continue
                seen_item.add(it_id)

                name = it.name or "Unnamed"
                
                # Improved description logic with fallback
                desc = (getattr(it, 'website_description', '') or '').strip()
                pt = getattr(it, 'product_id', False) and it.product_id or False
                
                # Clean HTML from menu item description first
                if desc:
                    import re
                    import html
                    
                    # Remove HTML tags (including malformed ones)
                    desc = re.sub(r'<[^<>]*>', '', desc)  # Standard tags
                    desc = re.sub(r'<[^>]*$', '', desc)   # Unclosed tags at end
                    desc = re.sub(r'^[^<]*>', '', desc)   # Unopened tags at start
                    desc = re.sub(r'</?[a-zA-Z][^>]*/?>', '', desc)  # Any remaining HTML-like tags
                    
                    # Remove any remaining angle brackets that might be leftover
                    desc = re.sub(r'[<>]', '', desc)
                    
                    # Decode HTML entities
                    desc = html.unescape(desc)
                    
                    # Clean up extra whitespace and newlines
                    desc = re.sub(r'\s+', ' ', desc).strip()
                    
                    # Remove common HTML artifacts
                    desc = re.sub(r'&nbsp;', ' ', desc)
                    desc = re.sub(r'&[a-zA-Z]+;', '', desc)  # Remove any remaining entities
                    
                    # Final cleanup
                    desc = desc.strip()
                
                # If no description from menu item, try product description fields
                if not desc and pt:
                    # Use same priority logic as grab_menu.py _compute_website_description
                    description_fields = [
                        'website_description',
                        'description_ecommerce', 
                        'public_description',
                        'description_sale',
                        'description'
                    ]
                    
                    for field_name in description_fields:
                         if hasattr(pt, field_name):
                             field_value = getattr(pt, field_name, None)
                             if field_value:
                                 candidate_desc = str(field_value).strip()
                                 
                                 # Check if this field contains JavaScript/code
                                 import re
                                 js_patterns = [
                                     r'document\.',
                                     r'addEventListener',
                                     r'querySelector',
                                     r'function\s*\(',
                                     r'const\s+\w+\s*=',
                                     r'let\s+\w+\s*=',
                                     r'var\s+\w+\s*=',
                                     r'=>',
                                     r'\.forEach\(',
                                     r'\.trim\(\)',
                                     r'innerText',
                                     r'innerHTML'
                                 ]
                                 
                                 # Skip if content looks like JavaScript code
                                 is_javascript = any(re.search(pattern, candidate_desc, re.IGNORECASE) for pattern in js_patterns)
                                 
                                 if not is_javascript:
                                     desc = candidate_desc
                                     break
                    
                    # Clean HTML tags and entities if present
                    if desc:
                        import re
                        import html
                        
                        # More comprehensive HTML tag removal
                        # Remove HTML tags (including malformed ones)
                        desc = re.sub(r'<[^<>]*>', '', desc)  # Standard tags
                        desc = re.sub(r'<[^>]*$', '', desc)   # Unclosed tags at end
                        desc = re.sub(r'^[^<]*>', '', desc)   # Unopened tags at start
                        desc = re.sub(r'</?[a-zA-Z][^>]*/?>', '', desc)  # Any remaining HTML-like tags
                        
                        # Remove any remaining angle brackets that might be leftover
                        desc = re.sub(r'[<>]', '', desc)
                        
                        # Decode HTML entities
                        desc = html.unescape(desc)
                        
                        # Clean up extra whitespace and newlines
                        desc = re.sub(r'\s+', ' ', desc).strip()
                        
                        # Remove common HTML artifacts
                        desc = re.sub(r'&nbsp;', ' ', desc)
                        desc = re.sub(r'&[a-zA-Z]+;', '', desc)  # Remove any remaining entities
                        
                        # Final cleanup
                        desc = desc.strip()
                        
                        # Final check: if result is too short or looks like code, clear it
                        if len(desc) < 10 or any(char in desc for char in ['{', '}', ';', '()', '=>']):
                            desc = ""
                
                # Debug logging for description being sent to Grab
                _logger.info(f"[GRAB WEBHOOK DEBUG] Item: {name} | Description length: {len(desc)} | First 200 chars: {desc[:200] if desc else 'EMPTY'}")

                # 价格：优先使用 Grab 专用价格（含 GST），否则回退到原逻辑
                base_price = None
                
                # 1. 首先检查是否有 Grab 专用价格设置
                if hasattr(it, 'use_grab_price') and it.use_grab_price and hasattr(it, 'grab_price_with_gst'):
                    base_price = it.grab_price_with_gst
                    _logger.info(f"[GRAB PRICING] Using Grab-specific price for {name}: {base_price} (incl. GST)")
                
                # 2. 回退到 item.price 字段
                if base_price is None:
                    base_price = getattr(it, 'price', None)
                
                # 3. 最后回退到产品模板价格（根据税务设置）
                if base_price is None and pt:
                    want_tax = str(_icp_get('grab.price_tax_included', '0') or '0').strip().lower() in ('1', 'true', 'yes')
                    base_price = _price_with_tax(pt) if want_tax else (pt.list_price or 0.0)
                    _logger.info(f"[GRAB PRICING] Using fallback price for {name}: {base_price} (tax_included: {want_tax})")

                img_url = _product_image_url(pt)
                _logger.info(
                    "GRAB MENU IMG: tmpl_id=%s name=%s has_img=%s url=%s",
                    pt.id if pt else None, name, bool(pt and pt.image_1920), img_url
                )

                # Debug logging for description content
                _logger.info(
                    "GRAB MENU DESC: item=%s desc_length=%s desc_content=%s",
                    name, len(desc), repr(desc[:200]) if desc else "EMPTY"
                )

                items.append({
                    "id": it_id,
                    "name": name,
                    "sequence": getattr(it, 'sequence', None) or 1,
                    "availableStatus": _norm_status(getattr(it, 'available_status', None), "AVAILABLE"),
                    "price": _int_cents(base_price),
                    "description": desc,
                    # 双保险：同时输出 imageUrl 与 photos（部分实现只看其一）
                    "imageUrl": img_url or "",
                    "photos": [img_url] if img_url else [],
                    "modifierGroups": _build_modifier_groups(it),
                })

            categories.append({
                "id": cat_id,
                "name": cat.name,
                "sequence": getattr(cat, 'sequence', None) or 1,
                "availableStatus": _norm_status(getattr(cat, 'available_status', None), "AVAILABLE"),
                "sellingTimeID": SELLING_TIME_ID,
                "items": items,
            })
    return categories

def _build_placeholder_category():
    Product = request.env['product.template'].sudo()
    p = Product.search([('website_published', '=', True)], limit=1)
    name = p.name if p else "Sample Item"
    price_cents = _int_cents(p.list_price if p else 1.00)
    url = _product_image_url(p) if p else ""
    return [{
        "id": "CATEGORY-PLACEHOLDER",
        "name": "Placeholder",
        "sequence": 1,
        "availableStatus": "AVAILABLE",
        "sellingTimeID": SELLING_TIME_ID,
        "items": [{
            "id": "ITEM-PLACEHOLDER",
            "name": name,
            "sequence": 1,
            "availableStatus": "AVAILABLE",
            "price": price_cents,
            "description": "Autogenerated placeholder to pass validation.",
            "imageUrl": url or "",
            "photos": [url] if url else [],
            "modifierGroups": []
        }]
    }]

def _build_selling_times():
    return [{
        "id": SELLING_TIME_ID,
        "name": "All Day",
        "sequence": 1,
        "serviceHours": {
            d: {
                "openPeriodType": "OpenPeriod",
                "periods": [{"startTime": "00:00", "endTime": "23:59"}]
            } for d in DAYS
        },
        "startTime": "1000-01-01 00:00:00",
        "endTime":   "9999-12-31 23:59:59"
    }]

def _build_payload(menu, grab_mid, pmid):
    effective_mid = grab_mid or (menu.merchant_id or "")
    effective_pmid = pmid or (menu.partner_merchant_id or "")

    selling_times = _build_selling_times()
    categories = _build_categories_from_db(menu)
    if not categories:
        categories = _build_placeholder_category()

    return {
        "merchantID": effective_mid,
        "partnerMerchantID": effective_pmid,
        "currency": {
            "code": menu.currency_code or "SGD",
            "symbol": menu.currency_symbol or "S$",
            "exponent": menu.currency_exponent or 2
        },
        "sellingTimes": selling_times,
        "categories": categories
    }

def _maybe_require_bearer():
    """grab.menu_require_auth ∈ {1,true,yes} 时对 Authorization: Bearer <token> 做校验"""
    req = str(_icp_get('grab.menu_require_auth', '0') or '0').strip().lower()
    require = req in ('1', 'true', 'yes')
    if not require:
        return None

    want = (_icp_get('grab.oauth.token') or '').strip()
    got = (request.httprequest.headers.get('Authorization', '') or '').strip()
    if not want:
        return None

    if not got.startswith('Bearer '):
        return request.make_response(
            json.dumps({"error": "Unauthorized"}, ensure_ascii=False),
            status=401, headers=[('Content-Type','application/json; charset=utf-8')]
        )
    token = got.split(' ', 1)[1].strip()
    if token != want:
        return request.make_response(
            json.dumps({"error": "Unauthorized"}, ensure_ascii=False),
            status=401, headers=[('Content-Type','application/json; charset=utf-8')]
        )
    return None

# -----------------------------
# Controller
# -----------------------------

class GrabMenuController(http.Controller):

    @http.route(
        [
            '/grab/get_menu', '/grab/get_menu/',
            '/grab/merchant/menu', '/grab/merchant/menu/',
        ],
        type='http', auth='public', csrf=False, methods=['GET', 'POST'], website=False
    )
    def get_menu(self, **kwargs):
        # 可选：对 Bearer 做校验
        auth_resp = _maybe_require_bearer()
        if auth_resp:
            return auth_resp

        grab_mid = _get_param('merchantID', 'merchantId', 'mid', default="")
        pmid = _get_param('partnerMerchantID', 'partnerMerchantId', 'pmid', default="")

        Menu = request.env['grab.menu'].sudo()
        menu = False
        if pmid:
            menu = Menu.search([('partner_merchant_id', '=', pmid)], limit=1)
        if not menu and grab_mid:
            menu = Menu.search([('merchant_id', '=', grab_mid)], limit=1)

        if not menu:
            menu = Menu.create({
                'name': f"Grab Menu ({pmid or grab_mid or 'NEW'})",
                'merchant_id': grab_mid,
                'partner_merchant_id': pmid
            })
        else:
            vals = {}
            if grab_mid and menu.merchant_id != grab_mid:
                vals['merchant_id'] = grab_mid
            if pmid and not menu.partner_merchant_id:
                vals['partner_merchant_id'] = pmid
            if vals:
                menu.write(vals)

        payload = _build_payload(menu, grab_mid, pmid)
        return request.make_response(
            json.dumps(payload, ensure_ascii=False),
            headers=[('Content-Type', 'application/json; charset=utf-8')]
        )
