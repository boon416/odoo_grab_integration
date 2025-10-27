# File: odoo_grab_integration/controllers/webhook_order.py
# -*- coding: utf-8 -*-

import json
import logging
from datetime import datetime


from odoo import http
from odoo.http import request, Response

_logger = logging.getLogger(__name__)

# ==== Helpers ====

def _parse_json_from_request():
    """兼容不同 Odoo/Werkzeug 版本的 JSON 解析。"""
    try:
        if request.httprequest.mimetype == 'application/json':
            jr = request.jsonrequest
            if isinstance(jr, dict):
                return jr
    except Exception:
        pass
    raw = b''
    try:
        raw = request.httprequest.data or b''
        if not raw and hasattr(request.httprequest, 'get_data'):
            raw = request.httprequest.get_data() or b''
    except Exception:
        raw = b''
    try:
        return json.loads((raw or b'').decode('utf-8') or '{}')
    except Exception:
        return {}

def _dt_iso_to_odoo(s):
    if not s or not str(s).strip():
        return False
    v = s[:-1] if isinstance(s, str) and s.endswith('Z') else s
    for fmt in ("%Y-%m-%dT%H:%M:%S.%f", "%Y-%m-%dT%H:%M:%S"):
        try:
            return datetime.strptime(v, fmt).strftime("%Y-%m-%d %H:%M:%S")
        except Exception:
            pass
    return False

def _json_response(payload, status=200):
    return Response(json.dumps(payload), status=status, headers=[("Content-Type", "application/json")])

def _bad_request(reason, details=None):
    payload = {"success": False, "reason": reason}
    if details: payload["details"] = details
    return _json_response(payload, status=400)

def _server_error(msg):
    return _json_response({"success": False, "reason": "server_error", "message": msg}, status=500)

# ==== Controller ====

class GrabOrderWebhookController(http.Controller):
    @http.route('/grab/webhook/order', type='http', auth='public', csrf=False, cors='*', methods=['POST'])
    def submit_order(self, **kwargs):
        try:
            data = _parse_json_from_request()

            # --- 基础校验（Best Practice #1）---
            required = ["orderID", "shortOrderNumber", "merchantID", "paymentType", "cutlery", "orderTime", "currency", "featureFlags", "items", "price"]
            missing = [k for k in required if k not in data]
            if missing:
                _logger.warning("SubmitOrder missing fields: %s payload=%s", missing, data)
                return _bad_request("missing_fields", missing)

            order_id = data["orderID"]

            # --- 幂等：命中即“更新”（Best Practice #2）---
            Order = request.env["grab.order"].sudo()
            Line  = request.env["grab.order.line"].sudo()
            MenuItem = request.env['grab.menu.item'].sudo()

            cur = data.get("currency") or {}
            currency_exponent = cur.get("exponent", 2)  # Default to 2 (cents)
            price_divisor = 10 ** currency_exponent  # e.g., 100 for SGD (10^2)
            
            vals = {
                "grab_order_id": order_id,
                "short_order_number": data.get("shortOrderNumber"),
                "merchant_id": data.get("merchantID"),
                "partner_merchant_id": data.get("partnerMerchantID"),
                "payment_type": data.get("paymentType"),
                "cutlery": data.get("cutlery"),
                "order_time": _dt_iso_to_odoo(data.get("orderTime")),
                "submit_time": _dt_iso_to_odoo(data.get("submitTime")),
                "complete_time": _dt_iso_to_odoo(data.get("completeTime")),
                "scheduled_time": _dt_iso_to_odoo(data.get("scheduledTime")),
                "order_state": data.get("orderState") or "",  # Submit payload 里通常为空
                "currency_code": cur.get("code"),
                "currency_symbol": cur.get("symbol"),
                "currency_exponent": currency_exponent,
                "feature_flags": data.get("featureFlags"),
                "dine_in": data.get("dineIn"),
                "receiver": data.get("receiver"),
                "order_ready_estimation": data.get("orderReadyEstimation"),
                "price_info": data.get("price"),
                "membership_id": data.get("membershipID") or "",
                "raw_json": data,
                # 记录编辑标志
                "is_mex_edit_order": bool((data.get("featureFlags") or {}).get("isMexEditOrder")),
            }

            rec = Order.search([("grab_order_id", "=", order_id)], limit=1)
            if rec:
                # 更新头
                rec.write(vals)
                # 清理并重建行（编辑单会替换最新明细）
                old_lines = rec.line_ids
                old_lines.unlink()
            else:
                rec = Order.create(vals)

            # 明细（不要把 "ITEM-xx" 当 Many2one 的 id）
            for item in (data.get("items") or []):
                # Convert modifier prices from minor units
                modifiers = item.get("modifiers") or []
                converted_modifiers = []
                for mod in modifiers:
                    mod_copy = dict(mod)  # Create a copy
                    if 'price' in mod_copy and mod_copy['price'] is not None:
                        mod_copy['price'] = mod_copy['price'] / price_divisor
                    if 'tax' in mod_copy and mod_copy['tax'] is not None:
                        mod_copy['tax'] = mod_copy['tax'] / price_divisor
                    converted_modifiers.append(mod_copy)

                # 统一提取与清洗外部标识
                grab_item_id = (item.get("grabItemID") or item.get("itemID") or item.get("itemId") or item.get("grabItemId") or "").strip()
                grab_item_code = (item.get("id") or item.get("itemCode") or item.get("code") or "").strip()

                # 先用 payload 自带的名称（若有）
                line_name = item.get("name") or item.get("shortName") or item.get("short_name") or ""

                search_code = grab_item_code or grab_item_id
                menu_item = MenuItem.search([('grab_item_code', '=', search_code)], limit=1) if search_code else MenuItem.browse()

                ProductProduct = request.env['product.product'].sudo()

                # 按 default_code / barcode 尝试匹配变体
                variant = ProductProduct.browse()
                if not menu_item and grab_item_code:
                    variant = ProductProduct.search([('default_code', '=', grab_item_code)], limit=1)
                if not variant and grab_item_id:
                    variant = ProductProduct.search([('default_code', '=', grab_item_id)], limit=1)
                if not variant and not menu_item:
                    barcode = (item.get('barcode') or "").strip()
                    if barcode:
                        variant = ProductProduct.search([('barcode', '=', barcode)], limit=1)
                if variant and not menu_item:
                    menu_item = MenuItem.search([('product_id', '=', variant.product_tmpl_id.id)], limit=1)

                # 最后兜底：名称至少填上可识别的ID
                product_name = (
                    menu_item.product_id.name
                    if menu_item and menu_item.product_id
                    else line_name
                    or search_code
                    or "Unknown Item"
                )

                if not line_name:
                    line_name = product_name

                _logger.info(
                    "Webhook item lookup: code=%s id=%s -> menu item=%s",
                    grab_item_code,
                    grab_item_id,
                    menu_item.display_name if menu_item else 'None',
                )

                Line.create({
                    "order_id": rec.id,
                    "grab_item_id": grab_item_id or False,
                    "grab_item_code": grab_item_code or False,
                    "name": line_name,
                    "product_id": menu_item.id if menu_item else False,
                    "product_name": product_name,
                    "quantity": item.get("quantity"),
                    "price": (item.get("price") or 0) / price_divisor,  # Convert from minor units
                    "tax": (item.get("tax") or 0) / price_divisor,  # Convert from minor units
                    "specifications": item.get("specifications") or "",
                    "out_of_stock_instruction": item.get("outOfStockInstruction"),
                    "modifiers": converted_modifiers,  # Modifiers with converted prices
                })

            # campaigns / promos 允许为 null
            Campaign = request.env['grab.order.campaign'].sudo()
            Promo    = request.env['grab.order.promo'].sudo()
            rec.campaign_ids.unlink()
            for c in (data.get("campaigns") or []):
                Campaign.create({
                    "order_id": rec.id,
                    "campaign_id": c.get("id"),
                    "name": c.get("name"),
                    "level": c.get("level"),
                    "type": c.get("type"),
                    "usage_count": c.get("usageCount"),
                    "mex_funded_ratio": c.get("mexFundedRatio"),
                    "deducted_amount": (c.get("deductedAmount") or 0) / price_divisor,  # Convert from minor units
                    "deducted_part": c.get("deductedPart"),
                    "campaign_name_for_mex": c.get("campaignNameForMex"),
                    "applied_item_ids": c.get("appliedItemIDs"),
                    "free_item": c.get("freeItem"),
                })
            rec.promo_ids.unlink()
            for p in (data.get("promos") or []):
                Promo.create({
                    "order_id": rec.id,
                    "code": p.get("code"),
                    "description": p.get("description"),
                    "name": p.get("name"),
                    "promo_amount": (p.get("promoAmount") or 0) / price_divisor,  # Convert from minor units
                    "mex_funded_ratio": p.get("mexFundedRatio"),
                    "mex_funded_amount": (p.get("mexFundedAmount") or 0) / price_divisor,  # Convert from minor units
                    "targeted_price": (p.get("targetedPrice") or 0) / price_divisor,  # Convert from minor units
                    "promo_amount_in_min": (p.get("promoAmountInMin") or 0) / price_divisor,  # Convert from minor units
                })

            _logger.info("SubmitOrder OK orderID=%s rec#%s mex_edit=%s", order_id, rec.id, rec.is_mex_edit_order)
            return _json_response({"success": True, "message": "synced", "order_id": rec.id}, status=200)

        except Exception as e:
            _logger.exception("SubmitOrder crashed: %s", e)
            return _server_error(str(e))
