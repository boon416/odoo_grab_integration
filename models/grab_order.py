from odoo import models, fields, api
from odoo.exceptions import UserError
from odoo.addons.odoo_grab_integration.push_grab_order_ready import push_grab_order_ready

class GrabOrder(models.Model):
    _name = 'grab.order'
    _description = 'Grab Order'

    grab_order_id = fields.Char('Order ID')
    short_order_number = fields.Char('Short Order Number')
    merchant_id = fields.Char('Merchant ID')
    partner_merchant_id = fields.Char('Partner Merchant ID')
    payment_type = fields.Char('Payment Type')
    cutlery = fields.Boolean('Cutlery')
    order_time = fields.Datetime('Order Time')
    submit_time = fields.Datetime('Submit Time')
    complete_time = fields.Datetime('Complete Time')
    scheduled_time = fields.Datetime('Scheduled Time')
    order_state = fields.Char('Order State')
    state_message = fields.Char('Order State Message')
    state_code = fields.Char('Order State Code')
    driver_eta = fields.Integer('Driver ETA (seconds)')

    # Currency fields
    currency_code = fields.Char('Currency Code')
    currency_symbol = fields.Char('Currency Symbol')
    currency_exponent = fields.Integer('Currency Exponent')

    # Feature flags as JSON
    feature_flags = fields.Json('Feature Flags')

    # Complex/nested fields as JSON
    dine_in = fields.Json('Dine In')
    receiver = fields.Json('Receiver')
    order_ready_estimation = fields.Json('Order Ready Estimation')
    price_info = fields.Json('Price Info')

    membership_id = fields.Char('Membership ID')

    # Related lines (one2many)
    line_ids = fields.One2many('grab.order.line', 'order_id', string='Order Items')
    campaign_ids = fields.One2many('grab.order.campaign', 'order_id', string='Campaigns')
    promo_ids = fields.One2many('grab.order.promo', 'order_id', string='Promos')

    # Store original JSON for reference/debug
    raw_json = fields.Json('Original JSON')

    # --- Compute fields for receiver ---
    receiver_name = fields.Char('Receiver Name', compute='_compute_receiver_name', store=False)
    receiver_phones = fields.Char('Receiver Phones', compute='_compute_receiver_phones', store=False)
    receiver_address = fields.Char('Receiver Address', compute='_compute_receiver_address', store=False)

    @api.depends('receiver')
    def _compute_receiver_name(self):
        for rec in self:
            rec.receiver_name = (rec.receiver or {}).get('name') if rec.receiver else ''

    @api.depends('receiver')
    def _compute_receiver_phones(self):
        for rec in self:
            rec.receiver_phones = (rec.receiver or {}).get('phones') if rec.receiver else ''

    @api.depends('receiver')
    def _compute_receiver_address(self):
        for rec in self:
            if rec.receiver and rec.receiver.get('address'):
                rec.receiver_address = rec.receiver['address'].get('address', '')
            else:
                rec.receiver_address = ''
    
    def action_push_order_ready(self):
        # 这个方法是 "Mark as Ready"
        self.ensure_one()
        client_id = self.env['ir.config_parameter'].sudo().get_param('grab.client_id')
        client_secret = self.env['ir.config_parameter'].sudo().get_param('grab.client_secret')
        status_code, resp_text = push_grab_order_ready(self.grab_order_id, client_id, client_secret, mark_status=1)
        if status_code == 204:
            msg = "Order marked as ready successfully (204 No Content)"
        else:
            msg = f"Failed: {status_code} {resp_text}"
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Push Order Status to Grab',
                'message': msg,
                'type': 'success' if status_code == 204 else 'danger',
                'sticky': False,
            }
        }
    def action_push_order_completed(self):
        self.ensure_one()
        client_id = self.env['ir.config_parameter'].sudo().get_param('grab.client_id')
        client_secret = self.env['ir.config_parameter'].sudo().get_param('grab.client_secret')
        status_code, resp_text = push_grab_order_ready(self.grab_order_id, client_id, client_secret, mark_status=2)
        if status_code == 204:
            # 成功后把Odoo订单状态也设为完成
            self.write({'order_state': 'COMPLETED'})  # 假设你的字段名是 order_state
            msg = "Order marked as completed successfully (204 No Content)"
            msg_type = 'success'
        else:
            msg = f"Failed: {status_code} {resp_text}"
            msg_type = 'danger'
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Push Order Status to Grab',
                'message': msg,
                'type': msg_type,
                'sticky': False,
            }
        }

class GrabOrderLine(models.Model):
    _name = 'grab.order.line'
    _description = 'Grab Order Line'

    order_id = fields.Many2one('grab.order', string='Order')
    item_id = fields.Many2one('grab.menu.item', string='Menu Item')
    grab_item_id = fields.Char('Grab Item ID')
    quantity = fields.Integer('Quantity')
    price = fields.Float('Price')
    tax = fields.Float('Tax')
    specifications = fields.Char('Specifications')
    # outOfStockInstruction、modifiers 推荐用Json存
    out_of_stock_instruction = fields.Json('Out of Stock Instruction')
    modifiers = fields.Json('Modifiers')
    modifier_names = fields.Char('Modifiers (Names)', compute='_compute_modifier_names', store=False)

    @api.depends('modifiers')
    def _compute_modifier_names(self):
        for rec in self:
            names = []
            if rec.modifiers:
                for m in rec.modifiers:
                    mod_code = m.get('id')
                    if mod_code:
                        # 用 code 字段找
                        modifier = self.env['grab.menu.modifier'].sudo().search([('modifier_code', '=', mod_code)], limit=1)
                        if modifier:
                            names.append(modifier.name)
            rec.modifier_names = ', '.join(names) if names else ''

class GrabOrderCampaign(models.Model):
    _name = 'grab.order.campaign'
    _description = 'Grab Order Campaign'

    order_id = fields.Many2one('grab.order', string='Order')
    name = fields.Char('Name')
    level = fields.Char('Level')
    type = fields.Char('Type')
    usage_count = fields.Integer('Usage Count')
    mex_funded_ratio = fields.Float('Mex Funded Ratio')
    deducted_amount = fields.Float('Deducted Amount')
    deducted_part = fields.Char('Deducted Part')
    campaign_name_for_mex = fields.Char('Campaign Name For Mex')
    applied_item_ids = fields.Json('Applied Item IDs')
    free_item = fields.Json('Free Item')
    # 还有id等字段，参考payload继续加
    campaign_id = fields.Char('Grab Campaign ID')

class GrabOrderPromo(models.Model):
    _name = 'grab.order.promo'
    _description = 'Grab Order Promo'

    order_id = fields.Many2one('grab.order', string='Order')
    code = fields.Char('Code')
    description = fields.Char('Description')
    name = fields.Char('Name')
    promo_amount = fields.Float('Promo Amount')
    mex_funded_ratio = fields.Float('Mex Funded Ratio')
    mex_funded_amount = fields.Float('Mex Funded Amount')
    targeted_price = fields.Float('Targeted Price')
    promo_amount_in_min = fields.Float('Promo Amount In Min')
