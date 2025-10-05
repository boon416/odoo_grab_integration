from odoo import models, fields, api, _
from odoo.addons.odoo_grab_integration.push_grab_menu_notification import push_grab_menu_notification
import requests
import json

from odoo.exceptions import UserError

# 路径按你的模块结构调整（utils 包路径以你现在的为准）
from ..utils.grab_oauth import grab_get_access_token
from ..utils.grab_activation import create_self_serve_activation

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
        ('SGD', 'SGD'), ('IDR', 'IDR'), ('MYR', 'MYR'), ('PHP', 'PHP'), ('THB', 'THB'), ('VND', 'VND')
    ], string="Currency Code", default="SGD")
    currency_symbol = fields.Char(string="Currency Symbol", default="S$")
    currency_exponent = fields.Integer(string="Currency Exponent", default=2)
    section_ids = fields.One2many('grab.menu.section', 'menu_id', string='Sections')
    last_menu_request_id = fields.Char()
    last_menu_job_id = fields.Char()
    
    def push_menu_to_grab(self):
        client_id = self.env['ir.config_parameter'].sudo().get_param('grab.client_id')
        client_secret = self.env['ir.config_parameter'].sudo().get_param('grab.client_secret')
        try:
            status_code, resp_text = push_grab_menu_notification(self.merchant_id, client_id, client_secret)
            if status_code == 204:
                message = "推送成功 (204 No Content)"
            else:
                message = f"推送失败: {status_code} {resp_text}"
        except Exception as e:
            message = f"推送异常: {str(e)}"
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Push to Grab',
                'message': message,
                'type': 'success' if '成功' in message else 'danger',
                'sticky': False,
            }
        }

    def action_activate_grab(self):
        """Launch Grab Self-Serve Activation and open the activation URL."""
        self.ensure_one()

        # 你存 Partner Merchant ID 的字段名可能不同，按你的模型改：
        pmid = getattr(self, 'partner_merchant_id', False) or getattr(self, 'merchant_partner_id', False)
        if not pmid:
            raise UserError(_("Please set Partner Merchant ID first."))

        icp = self.env['ir.config_parameter'].sudo()
        api_base = icp.get_param('grab.partner_api_base', 'https://partner-api.grab.com/grabfood/partner')

        # 用你已经写好的 client 拿 token（推荐方式）
        token = self.env['grab.api.client'].get_access_token()

        # 调你 utils 里的创建激活
        resp = create_self_serve_activation(pmid, token, base=api_base)

        # 兼容返回 string 或 dict 两种写法
        activation_url = resp if isinstance(resp, str) else (resp.get('activationUrl') or resp.get('url'))
        if not activation_url:
            raise UserError(_("No activation URL returned from Grab."))

        return {
            'type': 'ir.actions.act_url',
            'url': activation_url,
            'target': 'new',
        }

        def action_check_menu_trace(self):
            self.ensure_one()
            icp = self.env['ir.config_parameter'].sudo()
            base = icp.get_param('grab.partner_api_base', 'https://partner-api.grab.com/grabfood/partner')
            token = self.env['grab.api.client'].get_access_token()
            if not (self.last_menu_request_id or self.last_menu_job_id):
                raise UserError(_("No requestID/jobID recorded yet."))

            tries = []
            if self.last_menu_request_id:
                rid = self.last_menu_request_id
                tries += [("requestId", rid), ("requestID", rid)]
            if self.last_menu_job_id:
                jid = self.last_menu_job_id
                tries += [("jobId", jid), ("jobID", jid)]

            headers = {"Authorization": f"Bearer {token}"}
            last = None
            for key, val in tries:
                r = requests.get(f"{base}/partner/v1/merchant/menu/trace",
                                headers=headers, params={key: val}, timeout=15)
                last = (key, val, r.status_code, r.text)
                if 200 <= r.status_code < 300:
                    data = r.json() if r.text else {}
                    self.message_post(body=_("Menu trace (%s=%s):<br/><pre>%s</pre>") %
                                    (key, val, json.dumps(data, indent=2)))
                    return
            # 全部失败
            k, v, code, text = last or ("", "", 0, "")
            raise UserError(_("Trace failed (last try %s=%s): %s %s") % (k, v, code, text))

class GrabMenuSection(models.Model):
    _name = 'grab.menu.section'
    _description = 'Grab Menu Section'
    name = fields.Char(string="Section Name", required=True)
    menu_id = fields.Many2one('grab.menu', string="Menu", required=True)
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
    section_id = fields.Many2one('grab.menu.section', string='Section', required=True)
    item_ids = fields.One2many('grab.menu.item', 'category_id', string='Items')
    odoo_category_id = fields.Many2one('product.category', string='Odoo Category (for Sync)')

    def action_sync_odoo_products(self):
        for category in self:
            if not category.odoo_category_id:
                raise UserError("Please select an Odoo Category to sync products.")
            products = self.env['product.template'].search([
                ('categ_id', '=', category.odoo_category_id.id),
                ('website_published', '=', True)  # 加了这行！
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

    # 直接关联到产品模板（避免SKU混乱）
    product_id = fields.Many2one('product.template', string='Odoo Product', required=True)
    
    # 商品名称
    name = fields.Char(
        string="Product Name",
        related='product_id.name',
        store=False,
        readonly=True
    )
    # 商品价格
    price = fields.Float(
        related='product_id.list_price',
        store=False,
        readonly=True
    )
    # 商品简介（HTML）
    website_description = fields.Html(
        string="Website Description",
        compute='_compute_website_description',
        store=False,
        readonly=True
    )
    # 商品图片（直接Odoo图片字段）
    photo = fields.Image(
        related='product_id.image_128',
        store=False,
        readonly=True
    )
    # 图片URL（自动生成）
    photo_url = fields.Char(
        string='Photo URL',
        compute='_compute_photo_url',
        store=False,
        readonly=True
    )
    # Odoo类别
    product_category_id = fields.Many2one(
        related='product_id.categ_id',
        store=False,
        readonly=True,
        string="Odoo Category"
    )
    # Grab菜单分类
    category_id = fields.Many2one('grab.menu.category', string="Grab Category")
    # 状态&顺序
    available_status = fields.Selection([
        ('AVAILABLE', 'Available'), 
        ('UNAVAILABLE', 'Unavailable')
    ], default='AVAILABLE')
    sequence = fields.Integer(string="Sequence", default=1)
    # 修饰符组
    modifier_group_ids = fields.One2many(
        'grab.menu.modifier.group', 'item_id', string='Modifier Groups'
    )

    # 自动获取描述（防止没值报错）
    @api.depends('product_id.website_description')
    def _compute_website_description(self):
        for rec in self:
            rec.website_description = rec.product_id.website_description or ""
    # 自动生成图片URL（防呆+专业兼容）
    @api.depends('product_id')
    def _compute_photo_url(self):
        base_url = self.env['ir.config_parameter'].sudo().get_param('web.base.url')
        for rec in self:
            product = rec.product_id
            if product and product.image_1920:
                rec.photo_url = f"{base_url}/web/image/product.template/{product.id}/image_1920"
            else:
                rec.photo_url = ""
    @api.onchange('product_id')
    def _onchange_product_id_set_category(self):
        if self.product_id and self.product_id.categ_id:
            # 查找 Grab Category 有没有同名的
            grab_cat = self.env['grab.menu.category'].search([('name', '=', self.product_id.categ_id.name)], limit=1)
            if not grab_cat:
                # 创建新的 Grab Category，如果 section_id 必须填，可以默认选一个 Main Section
                section = self.env['grab.menu.section'].search([], limit=1)  # 选第一个section，实际可自定义
                grab_cat = self.env['grab.menu.category'].create({
                    'name': self.product_id.categ_id.name,
                    'section_id': section.id if section else False,
                })
            self.category_id = grab_cat.id

    def action_sync_modifiers_from_attributes(self):
        for rec in self:
            product = rec.product_id
            if not product:
                continue
            # 1. 删除已有的 modifier group（全覆盖同步，防止残留）
            rec.modifier_group_ids.unlink()
            # 2. 遍历产品的每个属性（比如 Size、Sugar Level 等）
            for attr_line in product.attribute_line_ids:
                # 创建 Modifier Group
                group = self.env['grab.menu.modifier.group'].create({
                    'name': attr_line.attribute_id.name,
                    'item_id': rec.id,
                    'group_code': f"{rec.id}_{attr_line.attribute_id.id}",
                    'available_status': 'AVAILABLE',
                    'selection_range_min': 0,
                    'selection_range_max': 1,
                })
                # 3. 遍历每个属性值（比如 L、M、100% Sugar）
                for value in attr_line.value_ids:
                    # 查找 ptav（product.template.attribute.value）记录，用于获取 price_extra
                    ptav = self.env['product.template.attribute.value'].search([
                        ('product_tmpl_id', '=', product.id),
                        ('product_attribute_value_id', '=', value.id)
                    ], limit=1)
                    extra_price = ptav.price_extra if ptav else 0.0
                    # 也可以 debug 一下
                    # import logging
                    # _logger = logging.getLogger(__name__)
                    # _logger.info("Modifier: %s, Extra Price: %s", value.name, extra_price)
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
    item_id = fields.Many2one('grab.menu.item', string='Menu Item', required=True)
    group_code = fields.Char('Modifier Group Code')  # 用于同步给Grab的id，建议有唯一性
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
    group_id = fields.Many2one('grab.menu.modifier.group', string='Modifier Group', required=True)
    modifier_code = fields.Char('Modifier Code')  # 同步Grab的id，建议唯一
    available_status = fields.Selection([
        ('AVAILABLE', 'Available'),
        ('UNAVAILABLE', 'Unavailable'),
        ('UNAVAILABLETODAY', 'Unavailable Today'),
        ('HIDE', 'Hide')
    ], default='AVAILABLE')
    price = fields.Float('Price')
    barcode = fields.Char('Barcode')
    # 可加 advanced_pricing JSON 字段等扩展