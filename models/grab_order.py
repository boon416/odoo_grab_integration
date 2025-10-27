import logging
from odoo import models, fields, api
from odoo.exceptions import UserError
from odoo.addons.odoo_grab_integration.push_grab_order_ready import push_grab_order_ready


_logger = logging.getLogger(__name__)

class GrabOrder(models.Model):
    _name = 'grab.order'
    _description = 'Grab Order'
    _rec_name = 'grab_order_id'

    grab_order_id = fields.Char('Order ID', required=True, index=True)
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
    is_mex_edit_order = fields.Boolean('Is MEX Edit Order', default=False,
                                       help='True if this order is an edited order from Merchant Experience (MEX)')

    # Related lines (one2many)
    line_ids = fields.One2many('grab.order.line', 'order_id', string='Order Items')
    campaign_ids = fields.One2many('grab.order.campaign', 'order_id', string='Campaigns')
    promo_ids = fields.One2many('grab.order.promo', 'order_id', string='Promos')

    # Store original JSON for reference/debug
    raw_json = fields.Json('Original JSON')

    _sql_constraints = [
        ('grab_order_id_unique', 'UNIQUE(grab_order_id)', 'Grab Order ID must be unique!')
    ]

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

    def _upsert_from_grab_json(self, data):
        """Upsert order from Grab JSON data (used by webhook and sync)"""
        self = self.sudo()
        order_id = data.get('orderID')
        if not order_id:
            return None
            
        # Helper function to parse ISO datetime
        def _dt_iso_to_odoo(s):
            if not s or not str(s).strip():
                return False
            from datetime import datetime
            v = s[:-1] if isinstance(s, str) and s.endswith('Z') else s
            for fmt in ("%Y-%m-%dT%H:%M:%S.%f", "%Y-%m-%dT%H:%M:%S"):
                try:
                    return datetime.strptime(v, fmt).strftime("%Y-%m-%d %H:%M:%S")
                except Exception:
                    pass
            return False
        
        # Get currency info and calculate divisor for price conversion
        # Grab returns prices in minor units (e.g., cents for SGD)
        cur = data.get('currency') or {}
        currency_exponent = cur.get('exponent', 2)  # Default to 2 (cents)
        price_divisor = 10 ** currency_exponent  # e.g., 100 for SGD (10^2)
        
        vals = {
            'grab_order_id': order_id,
            'short_order_number': data.get('shortOrderNumber'),
            'merchant_id': data.get('merchantID'),
            'partner_merchant_id': data.get('partnerMerchantID'),
            'payment_type': data.get('paymentType'),
            'cutlery': bool(data.get('cutlery')),
            'order_time': _dt_iso_to_odoo(data.get('orderTime')),
            'submit_time': _dt_iso_to_odoo(data.get('submitTime')),
            'complete_time': _dt_iso_to_odoo(data.get('completeTime')),
            'scheduled_time': _dt_iso_to_odoo(data.get('scheduledTime')),
            'order_state': data.get('orderState') or '',
            'currency_code': cur.get('code'),
            'currency_symbol': cur.get('symbol'),
            'currency_exponent': currency_exponent,
            'feature_flags': data.get('featureFlags'),
            'dine_in': data.get('dineIn'),
            'receiver': data.get('receiver'),
            'order_ready_estimation': data.get('orderReadyEstimation'),
            'price_info': data.get('price'),
            'membership_id': data.get('membershipID') or '',
            'raw_json': data,
            'is_mex_edit_order': bool((data.get('featureFlags') or {}).get('isMexEditOrder')),
        }
        
        rec = self.search([('grab_order_id', '=', order_id)], limit=1)
        if rec:
            rec.write(vals)
            # Clear existing lines, campaigns, promos
            rec.line_ids.unlink()
            rec.campaign_ids.unlink()
            rec.promo_ids.unlink()
        else:
            rec = self.create(vals)
        
        # Create order lines with price conversion
        Line = self.env['grab.order.line'].sudo()
        MenuItem = self.env['grab.menu.item'].sudo()  # Reference to grab.menu.item model
        for item in (data.get('items') or []):
            # Normalise every identifier we might receive from Grab
            grab_item_id = (
                item.get('grabItemID')
                or item.get('itemID')
                or item.get('itemId')
                or item.get('grabItemId')
                or ''
            ).strip()
            grab_item_code = (
                item.get('id')
                or item.get('itemCode')
                or item.get('code')
                or ''
            ).strip()
            search_code = grab_item_code or grab_item_id

            # Try to match the grab.menu.item record that already stores grab_item_code
            product = MenuItem.search([('grab_item_code', '=', search_code)], limit=1) if search_code else MenuItem.browse()

            # Fallback: Resolve through the corresponding product variant if the direct match fails
            if not product:
                ProductVariant = self.env['product.product'].sudo()
                variant = ProductVariant.search([('default_code', '=', grab_item_code)], limit=1) if grab_item_code else ProductVariant.browse()
                if not variant and grab_item_id:
                    variant = ProductVariant.search([('default_code', '=', grab_item_id)], limit=1)
                if not variant:
                    barcode = (item.get('barcode') or '').strip()
                    if barcode:
                        variant = ProductVariant.search([('barcode', '=', barcode)], limit=1)
                if variant:
                    product = MenuItem.search([('product_id', '=', variant.product_tmpl_id.id)], limit=1)

            product_name = product.product_id.name if product else (
                item.get('name')
                or item.get('shortName')
                or search_code
                or 'Unknown Item'
            )

            _logger.info(
                "Processing Grab item: code=%s id=%s -> menu item=%s",
                grab_item_code,
                grab_item_id,
                product.display_name if product else 'None',
            )
            
            modifiers = item.get('modifiers') or []
            converted_modifiers = []
            for mod in modifiers:
                mod_copy = dict(mod)  # Create a copy
                if 'price' in mod_copy and mod_copy['price'] is not None:
                    mod_copy['price'] = mod_copy['price'] / price_divisor
                if 'tax' in mod_copy and mod_copy['tax'] is not None:
                    mod_copy['tax'] = mod_copy['tax'] / price_divisor
                converted_modifiers.append(mod_copy)
                
            Line.create({
                'order_id': rec.id,
                'grab_item_id': grab_item_id or False,
                'grab_item_code': grab_item_code or False,
                'quantity': item.get('quantity'),
                'price': (item.get('price') or 0) / price_divisor,  # Convert from minor units
                'tax': (item.get('tax') or 0) / price_divisor,  # Convert from minor units
                'specifications': item.get('specifications') or '',
                'out_of_stock_instruction': item.get('outOfStockInstruction'),
                'modifiers': converted_modifiers,  # Modifiers with converted prices
                'product_id': product.id if product else False,  # Store product ID as Char
                'product_name': product_name,  # Optionally store product name
            })
        
        # Create campaigns with price conversion
        Campaign = self.env['grab.order.campaign'].sudo()
        for c in (data.get('campaigns') or []):
            Campaign.create({
                'order_id': rec.id,
                'campaign_id': c.get('id'),
                'name': c.get('name'),
                'level': c.get('level'),
                'type': c.get('type'),
                'usage_count': c.get('usageCount'),
                'mex_funded_ratio': c.get('mexFundedRatio'),
                'deducted_amount': (c.get('deductedAmount') or 0) / price_divisor,  # Convert from minor units
                'deducted_part': c.get('deductedPart'),
                'campaign_name_for_mex': c.get('campaignNameForMex'),
                'applied_item_ids': c.get('appliedItemIDs'),
                'free_item': c.get('freeItem'),
            })
        
        # Create promos with price conversion
        Promo = self.env['grab.order.promo'].sudo()
        for p in (data.get('promos') or []):
            Promo.create({
                'order_id': rec.id,
                'code': p.get('code'),
                'description': p.get('description'),
                'name': p.get('name'),
                'promo_amount': (p.get('promoAmount') or 0) / price_divisor,  # Convert from minor units
                'mex_funded_ratio': p.get('mexFundedRatio'),
                'mex_funded_amount': (p.get('mexFundedAmount') or 0) / price_divisor,  # Convert from minor units
                'targeted_price': (p.get('targetedPrice') or 0) / price_divisor,  # Convert from minor units
                'promo_amount_in_min': (p.get('promoAmountInMin') or 0) / price_divisor,  # Convert from minor units
            })
        
        return rec

class GrabOrderLine(models.Model):
    _name = 'grab.order.line'
    _description = 'Grab Order Line'

    order_id = fields.Many2one('grab.order', string='Order')

    # 保留为 Char，避免类型冲突 - 重命名避免与其他模型的item_id Many2one字段冲突
    grab_item_id = fields.Char('Grab Item ID')  # 这是外部/Grab的item标识，字符串
    grab_item_code = fields.Char('Grab Item Code')  # Grab内部代码

    # 如果你需要关联到 Odoo 的产品或你自定义的抓取模型，就新增一个不同名字的 M2O
    product_id = fields.Many2one('grab.menu.item', string='Product')  # Relational link to grab.menu.item
    product_name = fields.Char('Product Name')  # Optionally store product name as a Char field
    name = fields.Char('Name')
    short_name = fields.Char('Short Name')
    description = fields.Char('Description')
    quantity = fields.Integer('Quantity')
    unit_price = fields.Float('Unit Price')
    total_price = fields.Float('Total Price')
    price = fields.Float('Price')  # 单价字段，被webhook使用
    tax = fields.Float('Tax')  # 税费字段
    specifications = fields.Text('Specifications')  # 规格说明
    out_of_stock_instruction = fields.Text('Out of Stock Instruction')  # 缺货说明
    currency_code = fields.Char('Currency Code')
    currency_symbol = fields.Char('Currency Symbol')
    currency_exponent = fields.Integer('Currency Exponent')

    # JSON fields for options/modifiers
    options = fields.Json('Options')
    selected_options = fields.Json('Selected Options')
    images = fields.Json('Images')
    modifiers = fields.Json('Modifiers')  # 修饰符信息

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
