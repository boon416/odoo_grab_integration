# File: odoo_grab_integration/controllers/webhook_order_status.py
# -*- coding: utf-8 -*-

import json
import logging
from odoo import http
from odoo.http import request, Response

_logger = logging.getLogger(__name__)

def _parse_json_from_request():
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

def _json_response(payload, status=200):
    return Response(json.dumps(payload), status=status, headers=[("Content-Type", "application/json")])

def _bad_request(reason, details=None):
    payload = {"success": False, "reason": reason}
    if details: payload["details"] = details
    return _json_response(payload, status=400)

def _server_error(msg):
    return _json_response({"success": False, "reason": "server_error", "message": msg}, status=500)

class GrabOrderStatusWebhookController(http.Controller):
    @http.route('/grab/webhook/order/state', type='http', auth='public', csrf=False, cors='*', methods=['PUT','POST'])
    def push_order_state(self, **kwargs):
        try:
            data = _parse_json_from_request()
            order_id = data.get("orderID")
            if not order_id:
                _logger.warning("OrderState missing orderID: %s", data)
                return _bad_request("missing_fields", ["orderID"])

            state = data.get("state")
            code  = data.get("code")
            Order = request.env['grab.order'].sudo()
            rec = Order.search([('grab_order_id', '=', order_id)], limit=1)

            if not rec:
                # Best Practice: Return 409 to let Grab retry later or use manual sync
                _logger.warning("OrderState for unknown orderID=%s payload=%s", order_id, data)
                return _json_response({"success": False, "reason": "order_not_found"}, status=409)

            vals = {
                "order_state": state or rec.order_state,
                "state_code":  code  or rec.state_code,
                "state_message": data.get("message") or rec.state_message,
                "driver_eta":    data.get("driverETA") or rec.driver_eta,
            }
            rec.write(vals)

            _logger.info("OrderState OK orderID=%s state=%s code=%s", order_id, state, code)
            return _json_response({"success": True, "message": "state_updated"}, status=200)

        except Exception as e:
            _logger.exception("OrderState crashed: %s", e)
            return _server_error(str(e))
