# -*- coding: utf-8 -*-
import json
from odoo import http
from odoo.http import request
from datetime import datetime

def convert_odoo_datetime(dt):
    if not dt:
        return False
    if dt.endswith('Z'):
        dt = dt[:-1]
    try:
        return datetime.strptime(dt, "%Y-%m-%dT%H:%M:%S").strftime("%Y-%m-%d %H:%M:%S")
    except Exception:
        return False

def extract_int_item_id(grab_item_id):
    if grab_item_id and grab_item_id.startswith('ITEM-'):
        return int(grab_item_id.replace('ITEM-', ''))
    return None


class GrabOrderWebhookController(http.Controller):

    @http.route('/grab/webhook/order', type='http', auth='public', csrf=False, methods=['POST'])
    def grab_submit_order(self, **post):
        # 解析 JSON body
        try:
            data = json.loads(request.httprequest.data.decode('utf-8'))
        except Exception as e:
            return request.make_json_response({
                "success": False,
                "message": f"Invalid JSON: {str(e)}"
            })

        # 校验
        order_id = data.get('orderID')
        if not order_id:
            return request.make_json_response({"success": False, "message": "Missing orderID"})

        # --- Save order main info ---
        order_vals = {
            'grab_order_id': data.get('orderID'),
            'short_order_number': data.get('shortOrderNumber'),
            'merchant_id': data.get('merchantID'),
            'partner_merchant_id': data.get('partnerMerchantID'),
            'payment_type': data.get('paymentType'),
            'cutlery': data.get('cutlery'),
            'order_time': convert_odoo_datetime(data.get('orderTime')),
            'submit_time': convert_odoo_datetime(data.get('submitTime')),
            'complete_time': convert_odoo_datetime(data.get('completeTime')),
            'scheduled_time': convert_odoo_datetime(data.get('scheduledTime')),
            'order_state': data.get('orderState'),
            'currency_code': (data.get('currency') or {}).get('code'),
            'currency_symbol': (data.get('currency') or {}).get('symbol'),
            'currency_exponent': (data.get('currency') or {}).get('exponent'),
            'feature_flags': data.get('featureFlags'),
            'dine_in': data.get('dineIn'),
            'receiver': data.get('receiver'),
            'order_ready_estimation': data.get('orderReadyEstimation'),
            'price_info': data.get('price'),
            'membership_id': data.get('membershipID'),
            'raw_json': data,
        }
        order_rec = request.env['grab.order'].sudo().create(order_vals)

        # --- Items ---
        for item in data.get('items', []):
            odoo_item_id = extract_int_item_id(item.get('id'))
            request.env['grab.order.line'].sudo().create({
                'order_id': order_rec.id,
                'item_id': odoo_item_id,    # 这里是 Many2one 外键
                'grab_item_id': item.get('grabItemID'),
                'quantity': item.get('quantity'),
                'price': item.get('price'),
                'tax': item.get('tax'),
                'specifications': item.get('specifications'),
                'out_of_stock_instruction': item.get('outOfStockInstruction'),
                'modifiers': item.get('modifiers'),
            })

        # --- Campaigns ---
        for campaign in data.get('campaigns', []):
            request.env['grab.order.campaign'].sudo().create({
                'order_id': order_rec.id,
                'campaign_id': campaign.get('id'),
                'name': campaign.get('name'),
                'level': campaign.get('level'),
                'type': campaign.get('type'),
                'usage_count': campaign.get('usageCount'),
                'mex_funded_ratio': campaign.get('mexFundedRatio'),
                'deducted_amount': campaign.get('deductedAmount'),
                'deducted_part': campaign.get('deductedPart'),
                'campaign_name_for_mex': campaign.get('campaignNameForMex'),
                'applied_item_ids': campaign.get('appliedItemIDs'),
                'free_item': campaign.get('freeItem'),
            })

        # --- Promos ---
        for promo in data.get('promos', []):
            request.env['grab.order.promo'].sudo().create({
                'order_id': order_rec.id,
                'code': promo.get('code'),
                'description': promo.get('description'),
                'name': promo.get('name'),
                'promo_amount': promo.get('promoAmount'),
                'mex_funded_ratio': promo.get('mexFundedRatio'),
                'mex_funded_amount': promo.get('mexFundedAmount'),
                'targeted_price': promo.get('targetedPrice'),
                'promo_amount_in_min': promo.get('promoAmountInMin'),
            })

        return request.make_json_response({
            "success": True,
            "message": "Order received",
            "order_id": order_rec.id
        })
