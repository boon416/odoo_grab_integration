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
            missing = [k for k in required if not data.get(k)]
            if missing:
                _logger.warning("SubmitOrder missing fields: %s payload=%s", missing, data)
                return _bad_request("missing_fields", missing)

            order_id = data["orderID"]

            # --- 幂等：命中即“更新”（Best Practice #2）---
            Order = request.env["grab.order"].sudo()
            Line  = request.env["grab.order.line"].sudo()

            cur = data.get("currency") or {}
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
                "currency_exponent": cur.get("exponent"),
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
                modifiers = item.get("modifiers") or []
                Line.create({
                    "order_id": rec.id,
                    "item_id": False,                    # 后续映射到你本地菜单
                    "grab_item_id": item.get("grabItemID"),
                    "grab_item_code": item.get("id"),    # 建议模型有这个 Char 字段
                    "quantity": item.get("quantity"),
                    "price": item.get("price"),
                    "tax": item.get("tax"),
                    "specifications": item.get("specifications") or "",
                    "out_of_stock_instruction": item.get("outOfStockInstruction"),
                    "modifiers": modifiers,              # 若字段非 Json，请改为 json.dumps(modifiers)
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
                    "deducted_amount": c.get("deductedAmount"),
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
                    "promo_amount": p.get("promoAmount"),
                    "mex_funded_ratio": p.get("mexFundedRatio"),
                    "mex_funded_amount": p.get("mexFundedAmount"),
                    "targeted_price": p.get("targetedPrice"),
                    "promo_amount_in_min": p.get("promoAmountInMin"),
                })

            _logger.info("SubmitOrder OK orderID=%s rec#%s mex_edit=%s", order_id, rec.id, rec.is_mex_edit_order)
            return _json_response({"success": True, "message": "synced", "order_id": rec.id}, status=200)

        except Exception as e:
            _logger.exception("SubmitOrder crashed: %s", e)
            return _server_error(str(e))
