# models/grab_menu.py
# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import UserError
import json
import requests

# 工具：获取 Grab 访问令牌、创建 SSA 激活、通知菜单更新
from ..utils.grab_oauth import grab_get_access_token
from ..utils.grab_activation import create_self_serve_activation
from ..utils.push_menu_notification import push_menu_notification


class GrabMenu(models.Model):
    _name = 'grab.menu'
    _description = 'Grab Menu'

    name = fields.Char(string="Menu Name", required=True)
    merchant_id = fields.Char(string="Merchant ID", required=True)
    partner_merchant_id = fields.Char(string="Partner Merchant ID")

    integration_status = fields.Selection([
        ('PENDING', 'Pending'),
        ('ACTIVE', 'Active'),
        ('INACTIVE', 'Inactive'),
        ('REJECTED', 'Rejected'),
        ('SUSPENDED', 'Suspended'),
    ], string="Integration Status")

    currency_code = fields.Selection([
        ('SGD', 'SGD'), ('IDR', 'IDR'), ('MYR', 'MYR'),
        ('PHP', 'PHP'), ('THB', 'THB'), ('VND', 'VND')
    ], string="Currency Code", default="SGD")
    currency_symbol = fields.Char(string="Currency Symbol", default="S$")
    currency_exponent = fields.Integer(string="Currency Exponent", default=2)

    section_ids = fields.One2many('grab.menu.section', 'menu_id', string='Sections')

    # Trace（可选）
    last_menu_request_id = fields.Char()
    last_menu_job_id = fields.Char()

    # -------------------------------
    # 按钮：推送菜单（实际=通知 Grab 你更新了菜单；Grab 会来拉 GetMenu）
    # -------------------------------
    def push_menu_to_grab(self):
        self.ensure_one()
        if not self.merchant_id:
            raise UserError(_("Please set Grab merchantID on this menu record."))

        try:
            code, text = push_menu_notification(self.env, self.merchant_id)
            if code == 204:
                msg = _("Push OK (204 No Content). Grab will fetch the latest menu from our GetMenu endpoint.")
                t = 'success'
            elif code == 409:
                msg = _("Too frequent (409). Please retry after ~120 seconds.")
                t = 'warning'
            else:
                msg = _("Push failed: %s %s") % (code, text or "")
                t = 'danger'
        except Exception as e:
            msg = _("Push exception: %s") % str(e)
            t = 'danger'

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {'title': 'Push to Grab', 'message': msg, 'type': t, 'sticky': False}
        }

    # -------------------------------
    # 按钮：启动 Self-Serve Activation（打开激活 URL）
    # -------------------------------
    def action_activate_grab(self):
        self.ensure_one()
        pmid = self.partner_merchant_id
        if not pmid:
            raise UserError(_("Please set Partner Merchant ID first."))

        icp = self.env['ir.config_parameter'].sudo()
        api_base = icp.get_param('grab.partner_api_base', 'https://partner-api.grab.com/grabfood/partner')

        token = grab_get_access_token(self.env)
        resp = create_self_serve_activation(pmid, token, base=api_base)

        activation_url = resp if isinstance(resp, str) else (resp.get('activationUrl') or resp.get('url'))
        if not activation_url:
            raise UserError(_("No activation URL returned from Grab."))

        return {'type': 'ir.actions.act_url', 'url': activation_url, 'target': 'new'}

    # -------------------------------
    # 按钮：查看菜单同步轨迹（调试用）
    # -------------------------------
    def action_check_menu_trace(self):
        self.ensure_one()
        if not (self.last_menu_request_id or self.last_menu_job_id):
            raise UserError(_("No requestID/jobID recorded yet."))

        icp = self.env['ir.config_parameter'].sudo()
        base = icp.get_param('grab.partner_api_base', 'https://partner-api.grab.com/grabfood/partner')
        token = grab_get_access_token(self.env)

        headers = {"Authorization": f"Bearer {token}"}
        tries = []
        if self.last_menu_request_id:
            rid = self.last_menu_request_id
            tries += [("requestId", rid), ("requestID", rid)]
        if self.last_menu_job_id:
            jid = self.last_menu_job_id
            tries += [("jobId", jid), ("jobID", jid)]

        last = None
        for key, val in tries:
            r = requests.get(f"{base}/partner/v1/merchant/menu/trace", headers=headers, params={key: val}, timeout=20)
            last = (key, val, r.status_code, r.text)
            if 200 <= r.status_code < 300:
                data = r.json() if (r.text or "").strip() else {}
                self.message_post(body=_("Menu trace (%s=%s):<br/><pre>%s</pre>") %
                                       (key, val, json.dumps(data, indent=2)))
                return
        k, v, code, text = last or ("", "", 0, "")
        raise UserError(_("Trace failed (last try %s=%s): %s %s") % (k, v, code, text))


# ===================== 子模型：菜单结构 =====================

class GrabMenuSection(models.Model):
    _name = 'grab.menu.section'
    _description = 'Grab Menu Section'

    name = fields.Char(string="Section Name", required=True)
    menu_id = fields.Many2one('grab.menu', string="Menu", required=True, ondelete='cascade')
    sequence = fields.Integer(string="Sequence", default=1)
    service_hours_json = fields.Text(string="Service Hours (JSON)", default=lambda self: self._default_service_hours())
    category_ids = fields.One2many('grab.menu.category', 'section_id', string='Categories')

    def _default_service_hours(self):
        default = {
            day: {
                "openPeriodType": "OpenPeriod",
                "periods": [{"startTime": "07:00", "endTime": "23:00"}]
            } for day in ['mon', 'tue', 'wed', 'thu', 'fri', 'sat', 'sun']
        }
        return json.dumps(default, indent=2)


class GrabMenuCategory(models.Model):
    _name = 'grab.menu.category'
    _description = 'Grab Menu Category'

    name = fields.Char(string="Category Name", required=True)
    sequence = fields.Integer(string="Sequence", default=1)
    section_id = fields.Many2one('grab.menu.section', string='Section', required=True, ondelete='cascade')
    item_ids = fields.One2many('grab.menu.item', 'category_id', string='Items')
    odoo_category_id = fields.Many2one('product.category', string='Odoo Category (for Sync)')

    def action_sync_odoo_products(self):
        for category in self:
            if not category.odoo_category_id:
                raise UserError(_("Please select an Odoo Category to sync products."))
            products = self.env['product.template'].search([
                ('categ_id', '=', category.odoo_category_id.id),
                ('active', '=', True),
                ('sale_ok', '=', True),
            ])
            for product in products:
                exist = self.env['grab.menu.item'].search([
                    ('product_id', '=', product.id),
                    ('category_id', '=', category.id)
                ], limit=1)
                if not exist:
                    self.env['grab.menu.item'].create({
                        'product_id': product.id,
                        'category_id': category.id,
                    })

    def action_sync_modifiers_for_all_items(self):
        for item in self.item_ids:
            item.action_sync_modifiers_from_attributes()


class GrabMenuItem(models.Model):
    _name = 'grab.menu.item'
    _description = 'Grab Menu Item'

    product_id = fields.Many2one('product.template', string='Odoo Product', required=True)

    # 供视图显示图片用（修复 view 的 <field name="photo" widget="image"/>）
    photo = fields.Image(string="Photo", related='product_id.image_1920', readonly=True, store=False)

    # 展示字段
    name = fields.Char(string="Product Name", related='product_id.name', store=False, readonly=True)
    price = fields.Float(related='product_id.list_price', store=False, readonly=True)
    website_description = fields.Html(string="Website Description",
                                      compute='_compute_website_description', store=False, readonly=True,
                                      help="Auto-populated from product description fields")
    photo_url = fields.Char(string='Photo URL', compute='_compute_photo_url', store=False, readonly=True)
    product_category_id = fields.Many2one(related='product_id.categ_id', store=False, readonly=True,
                                          string="Odoo Category")
    
    # Grab-specific pricing fields
    grab_price = fields.Float(string="Grab Price (Excl. GST)", 
                              help="Custom price for Grab platform (excluding GST)")
    gst_rate = fields.Float(string="GST Rate (%)", default=7.0,
                           help="GST rate percentage (default 7% for Singapore)")
    grab_price_with_gst = fields.Float(string="Grab Price (Incl. GST)", 
                                       compute='_compute_grab_price_with_gst', store=False,
                                       help="Final price sent to Grab including GST")
    use_grab_price = fields.Boolean(string="Use Custom Grab Price", default=False,
                                   help="If enabled, uses grab_price instead of product list_price")

    category_id = fields.Many2one('grab.menu.category', string="Grab Category", ondelete='set null')
    available_status = fields.Selection([
        ('AVAILABLE', 'Available'),
        ('UNAVAILABLE', 'Unavailable')
    ], default='AVAILABLE')
    sequence = fields.Integer(string="Sequence", default=1)

    modifier_group_ids = fields.One2many('grab.menu.modifier.group', 'item_id', string='Modifier Groups')

    @api.depends('grab_price', 'gst_rate', 'use_grab_price', 'product_id.list_price')
    def _compute_grab_price_with_gst(self):
        """Compute the final Grab price including GST"""
        for rec in self:
            if rec.use_grab_price and rec.grab_price:
                # Use custom Grab price
                base_price = rec.grab_price
            else:
                # Use product list price as fallback
                base_price = rec.product_id.list_price if rec.product_id else 0.0
            
            # Calculate GST
            gst_amount = base_price * (rec.gst_rate / 100.0)
            rec.grab_price_with_gst = base_price + gst_amount

    @api.depends('product_id.website_description', 'product_id.description_sale', 'product_id.description',
                 'product_id.description_ecommerce', 'product_id.public_description')
    def _compute_website_description(self):
        for rec in self:
            desc = ""
            if rec.product_id:
                # Priority order for description fields (only existing fields)
                description_fields = [
                    'website_description',      # Website-specific description (highest priority)
                    'description_ecommerce',    # Ecommerce description
                    'public_description',       # Public description
                    'description_sale',         # Sales description
                    'description',              # Main description (fallback)
                ]
                
                # Try each field in priority order
                for field_name in description_fields:
                    if hasattr(rec.product_id, field_name):
                        field_value = getattr(rec.product_id, field_name, None)
                        if field_value and field_value.strip():
                            candidate_desc = field_value.strip()
                            
                            # Clean HTML tags, JavaScript, and other unwanted content
                            import re
                            import html
                            
                            # Skip if content looks like JavaScript/code (contains common JS patterns)
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
                            
                            # Check if description contains JavaScript code
                            is_javascript = any(re.search(pattern, candidate_desc, re.IGNORECASE) for pattern in js_patterns)
                            
                            if is_javascript:
                                # Skip this field and continue to next one
                                continue
                            
                            # More comprehensive HTML tag removal
                            # Remove HTML tags (including malformed ones)
                            candidate_desc = re.sub(r'<[^<>]*>', '', candidate_desc)  # Standard tags
                            candidate_desc = re.sub(r'<[^>]*$', '', candidate_desc)   # Unclosed tags at end
                            candidate_desc = re.sub(r'^[^<]*>', '', candidate_desc)   # Unopened tags at start
                            candidate_desc = re.sub(r'</?[a-zA-Z][^>]*/?>', '', candidate_desc)  # Any remaining HTML-like tags
                            
                            # Remove any remaining angle brackets that might be leftover
                            candidate_desc = re.sub(r'[<>]', '', candidate_desc)
                            
                            # Decode HTML entities (like &amp;, &lt;, etc.)
                            candidate_desc = html.unescape(candidate_desc)
                            
                            # Clean up extra whitespace and newlines
                            candidate_desc = re.sub(r'\s+', ' ', candidate_desc).strip()
                            
                            # Remove common HTML artifacts
                            candidate_desc = re.sub(r'&nbsp;', ' ', candidate_desc)
                            candidate_desc = re.sub(r'&[a-zA-Z]+;', '', candidate_desc)  # Remove any remaining entities
                            
                            # Final cleanup
                            candidate_desc = candidate_desc.strip()
                            
                            # Final check: if result is too short or looks like code, skip it
                            if len(candidate_desc) < 10 or any(char in candidate_desc for char in ['{', '}', ';', '()', '=>']):
                                continue
                            
                            # If we get here, we have a valid description
                            desc = candidate_desc
                            break
                    
            # Always assign a value to the field (even if empty string)
            rec.website_description = desc



    @api.depends('product_id', 'product_id.image_1920', 'product_id.image_1024', 'product_id.image_512')
    def _compute_photo_url(self):
        base_url = self.env['ir.config_parameter'].sudo().get_param('web.base.url')
        for rec in self:
            p = rec.product_id
            if p:
                # Try different image sizes in order of preference
                if p.image_1920:
                    rec.photo_url = f"{base_url}/web/image/product.template/{p.id}/image_1920"
                elif p.image_1024:
                    rec.photo_url = f"{base_url}/web/image/product.template/{p.id}/image_1024"
                elif p.image_512:
                    rec.photo_url = f"{base_url}/web/image/product.template/{p.id}/image_512"
                else:
                    rec.photo_url = ""
            else:
                rec.photo_url = ""

    @api.onchange('product_id')
    def _onchange_product_id_set_category(self):
        """Auto-set category based on product category when product changes"""
        if self.product_id and self.product_id.categ_id:
            # Try to find a matching grab category
            grab_category = self.env['grab.menu.category'].search([
                ('odoo_category_id', '=', self.product_id.categ_id.id)
            ], limit=1)
            if grab_category:
                self.category_id = grab_category.id
        
        # Also trigger description computation
        self._compute_website_description()

    def action_set_grab_price_from_product(self):
        """Set Grab price based on product list price with optional markup"""
        return {
            'type': 'ir.actions.act_window',
            'name': 'Set Grab Price',
            'res_model': 'grab.price.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_item_ids': [(6, 0, self.ids)],
                'default_markup_percentage': 20.0,  # Default 20% markup for platform fees
            }
        }

    def action_copy_product_price_to_grab(self):
        """Copy product list price to grab price (1:1 ratio)"""
        for rec in self:
            if rec.product_id:
                rec.grab_price = rec.product_id.list_price
                rec.use_grab_price = True
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Prices Updated',
                'message': f'Copied product prices to Grab prices for {len(self)} items',
                'type': 'success',
            }
        }

    def action_calculate_grab_price_with_markup(self, markup_percentage=20.0):
        """Calculate Grab price with markup percentage"""
        for rec in self:
            if rec.product_id:
                base_price = rec.product_id.list_price
                markup_amount = base_price * (markup_percentage / 100.0)
                rec.grab_price = base_price + markup_amount
                rec.use_grab_price = True

    def action_sync_modifiers_from_attributes(self):
        for rec in self:
            product = rec.product_id
            if not product:
                continue
            # 覆盖式同步
            rec.modifier_group_ids.unlink()
            for attr_line in product.attribute_line_ids:
                group = self.env['grab.menu.modifier.group'].create({
                    'name': attr_line.attribute_id.name,
                    'item_id': rec.id,
                    'group_code': f"{rec.id}_{attr_line.attribute_id.id}",
                    'available_status': 'AVAILABLE',
                    'selection_range_min': 1,
                    'selection_range_max': 1,
                })
                for value in attr_line.value_ids:
                    ptav = self.env['product.template.attribute.value'].search([
                        ('product_tmpl_id', '=', product.id),
                        ('product_attribute_value_id', '=', value.id)
                    ], limit=1)
                    extra_price = ptav.price_extra if ptav else 0.0
                    self.env['grab.menu.modifier'].create({
                        'name': value.name,
                        'group_id': group.id,
                        'modifier_code': f"{group.id}_{value.id}",
                        'available_status': 'AVAILABLE',
                        'price': extra_price,
                        'barcode': value.name,
                    })


class GrabMenuModifierGroup(models.Model):
    _name = 'grab.menu.modifier.group'
    _description = 'Grab Menu Modifier Group'

    name = fields.Char('Modifier Group Name', required=True)
    item_id = fields.Many2one('grab.menu.item', string='Menu Item', required=True, ondelete='cascade')
    group_code = fields.Char('Modifier Group Code')
    available_status = fields.Selection([
        ('AVAILABLE', 'Available'),
        ('UNAVAILABLE', 'Unavailable'),
        ('UNAVAILABLETODAY', 'Unavailable Today'),
        ('HIDE', 'Hide')
    ], default='AVAILABLE')
    selection_range_min = fields.Integer('Selection Range Min', default=0)
    selection_range_max = fields.Integer('Selection Range Max', default=1)
    modifier_ids = fields.One2many('grab.menu.modifier', 'group_id', string='Modifiers')


class GrabMenuModifier(models.Model):
    _name = 'grab.menu.modifier'
    _description = 'Grab Menu Modifier'

    name = fields.Char('Modifier Name', required=True)
    group_id = fields.Many2one('grab.menu.modifier.group', string='Modifier Group', required=True, ondelete='cascade')
    modifier_code = fields.Char('Modifier Code')
    available_status = fields.Selection([
        ('AVAILABLE', 'Available'),
        ('UNAVAILABLE', 'Unavailable'),
        ('UNAVAILABLETODAY', 'Unavailable Today'),
        ('HIDE', 'Hide')
    ], default='AVAILABLE')
    price = fields.Float('Price')
    barcode = fields.Char('Barcode')
