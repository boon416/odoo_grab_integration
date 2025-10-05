# -*- coding: utf-8 -*-
import json
from odoo import http
from odoo.http import request

class GrabOrderStatusWebhookController(http.Controller):

    @http.route('/grab/webhook/order/state', type='http', auth='public', csrf=False, methods=['PUT'])
    def grab_push_order_state(self, **post):
        try:
            data = json.loads(request.httprequest.data.decode('utf-8'))
        except Exception as e:
            return request.make_json_response({
                "success": False,
                "message": f"Invalid JSON: {str(e)}"
            }, 400)

        order_id = data.get('orderID')
        state = data.get('state')
        if not order_id or not state:
            return request.make_json_response({"success": False, "message": "Missing orderID or state"}, 400)

        order = request.env['grab.order'].sudo().search([('grab_order_id', '=', order_id)], limit=1)
        if not order:
            return request.make_json_response({"success": False, "message": "Order not found"}, 404)

        # 你可以按需添加/修改字段名
        update_vals = {
            'order_state': state,
            'state_message': data.get('message'),
            'state_code': data.get('code'),
            'driver_eta': data.get('driverETA'),
        }
        order.write(update_vals)

        return request.make_json_response({
            "success": True,
            "message": "Order state updated"
        })
