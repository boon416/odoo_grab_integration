# models/grab_order_sync.py
import requests
from odoo import models, fields, api, _
from odoo.exceptions import UserError
from datetime import date, timedelta

class GrabOrderSync(models.TransientModel):
    _name = 'grab.order.sync.wizard'
    _description = 'Sync Grab Orders (List Orders)'

    sync_date = fields.Date(default=lambda self: fields.Date.context_today(self))

    def action_sync(self):
        self.ensure_one()
        ICP = self.env['ir.config_parameter'].sudo()
        client_id = ICP.get_param('grab.client_id')
        client_secret = ICP.get_param('grab.client_secret')
        merchant_id = ICP.get_param('grab.merchant_id')
        if not all([client_id, client_secret, merchant_id]):
            raise UserError(_("Missing Grab config (client_id/secret/merchant_id)."))

        # 1) 取 token（用你现有的 grab_get_access_token）
        from ..utils.grab_oauth import grab_get_access_token
        token = grab_get_access_token(client_id, client_secret)

        # 2) 翻页拉单
        headers = {'Authorization': f'Bearer {token}'}
        base = 'https://partner-api.grab.com/grabfood/partner/v1/orders'
        page = 0
        any_count = 0
        while True:
            params = {
                'merchantID': merchant_id,
                'date': self.sync_date.strftime('%Y-%m-%d'),
                'page': page,
            }
            resp = requests.get(base, headers=headers, params=params, timeout=20)
            if resp.status_code != 200:
                raise UserError(_("Grab list orders failed: %s %s") % (resp.status_code, resp.text))
            payload = resp.json() or {}
            orders = payload.get('orders') or []
            # 3) 复用“提交订单”解析逻辑，把单落地
            for order_json in orders:
                self.env['grab.order']._upsert_from_grab_json(order_json)  # 见下方方法
            any_count += len(orders)
            if not payload.get('more'):
                break
            page += 1

        # 提示
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _("Grab Orders Sync"),
                'message': _("Synced %s orders for %s") % (any_count, self.sync_date),
                'type': 'success',
            }
        }

# models/grab_order.py（新增一个可复用的 upsert 方法）
from odoo import models, fields, api

class GrabOrder(models.Model):
    _name = 'grab.order'
    # ... 省略字段（你已有）

    def _upsert_from_grab_json(self, data):
        """把 Grab 的订单 JSON 写进 grab.order。
        这里直接复用你 submit webhook 的写入逻辑，确保幂等。"""
        self = self.sudo()
        order_id = data.get('orderID')
        vals = {
            'grab_order_id': order_id,
            'short_order_number': data.get('shortOrderNumber'),
            'merchant_id': data.get('merchantID'),
            'partner_merchant_id': data.get('partnerMerchantID'),
            'payment_type': data.get('paymentType'),
            'cutlery': bool(data.get('cutlery')),
            # 时间字段解析同你 webhook 控制器的 _dt_iso_to_dt
            # ...
            'order_state': data.get('orderState') or '',
            'feature_flags': data.get('featureFlags'),
            'receiver': data.get('receiver'),
            'price_info': data.get('price'),
            'raw_json': data,
        }
        rec = self.search([('grab_order_id', '=', order_id)], limit=1)
        if rec:
            rec.write(vals)
            rec.line_ids.unlink(); rec.campaign_ids.unlink(); rec.promo_ids.unlink()
        else:
            rec = self.create(vals)
        for item in (data.get('items') or []):
            self.env['grab.order.line'].create({
                'order_id': rec.id,
                'grab_item_id': item.get('grabItemID'),
                'grab_item_code': item.get('id'),
                'quantity': item.get('quantity'),
                'price': item.get('price'),
                'tax': item.get('tax') or 0,
                'specifications': item.get('specifications') or '',
                'modifiers': item.get('modifiers') or [],
            })
        # promos/campaigns 同你当前逻辑
        return rec
