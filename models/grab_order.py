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
    is_mex_edit_order = fields.Boolean('Is MEX Edit Order', default=False)

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
            rec.receiver_address = (rec.receiver or {}).get('address') if rec.receiver else ''

    # ========= Buttons to push status to Grab =========
    def action_push_order_ready(self):
        self.ensure_one()
        if not self.grab_order_id:
            raise UserError('Missing Grab Order ID')
        status_code, resp_text = push_grab_order_ready(self.env, self.grab_order_id)
        if status_code == 204:
            msg = "Success: Grab acknowledged order ready."
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
        # TODO: implement push completed if needed
        raise UserError('Not implemented')

class GrabOrderLine(models.Model):
    _name = 'grab.order.line'
    _description = 'Grab Order Line'

    order_id = fields.Many2one('grab.order', string='Order')

    # 保留为 Char，避免类型冲突
    item_id = fields.Char('Item ID')  # 这是外部/Grab的item标识，字符串

    # 如果你需要关联到 Odoo 的产品或你自定义的抓取模型，就新增一个不同名字的 M2O
    product_id = fields.Many2one('product.product', string='Linked Product')  # 或者 'grab.menu.item'
    name = fields.Char('Name')
    short_name = fields.Char('Short Name')
    description = fields.Char('Description')
    quantity = fields.Integer('Quantity')
    unit_price = fields.Float('Unit Price')
    total_price = fields.Float('Total Price')
    currency_code = fields.Char('Currency Code')
    currency_symbol = fields.Char('Currency Symbol')
    currency_exponent = fields.Integer('Currency Exponent')

    # JSON fields for options/modifiers
    options = fields.Json('Options')
    selected_options = fields.Json('Selected Options')
    images = fields.Json('Images')

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
