# models/product_template_grab.py
# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import UserError


class ProductTemplateGrab(models.Model):
    _inherit = 'product.template'

    # Grab-related fields
    grab_menu_item_ids = fields.One2many('grab.menu.item', 'product_id', string='Grab Menu Items')
    grab_menu_item_count = fields.Integer(string='Grab Items Count', compute='_compute_grab_menu_item_count', store=True)
    
    # Custom Grab pricing
    use_grab_price = fields.Boolean(string="Use Custom Grab Price", default=False,
                                   help="If enabled, uses custom grab_price instead of product list_price")
    grab_price = fields.Float(string="Grab Price (Excl. GST)", 
                             help="Custom price for Grab platform (excluding GST)")
    gst_rate = fields.Float(string="GST Rate (%)", default=7.0,
                           help="GST rate percentage (default 7% for Singapore)")
    grab_price_with_gst = fields.Float(string="Grab Price (Incl. GST)", 
                                      compute='_compute_grab_price_with_gst', store=False,
                                      help="Final price sent to Grab including GST")
    
    # Grab availability
    grab_available = fields.Boolean(string="Available on Grab", default=True,
                                   help="Toggle to make this product available/unavailable on Grab")
    
    # Sync settings
    grab_sync_enabled = fields.Boolean(string="Enable Grab Sync", default=True,
                                      help="Automatically sync product changes to linked Grab menu items")

    @api.depends('grab_menu_item_ids')
    def _compute_grab_menu_item_count(self):
        for product in self:
            product.grab_menu_item_count = len(product.grab_menu_item_ids)

    @api.depends('grab_price', 'gst_rate', 'use_grab_price', 'list_price')
    def _compute_grab_price_with_gst(self):
        for product in self:
            if product.use_grab_price and product.grab_price:
                base_price = product.grab_price
            else:
                base_price = product.list_price
            
            gst_multiplier = 1 + (product.gst_rate / 100)
            product.grab_price_with_gst = base_price * gst_multiplier

    def action_view_grab_menu_items(self):
        """Open the list of Grab menu items for this product"""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': f'Grab Menu Items for {self.name}',
            'res_model': 'grab.menu.item',
            'view_mode': 'list,form',
            'domain': [('product_id', '=', self.id)],
            'context': {'default_product_id': self.id},
            'view_id': False,  # Let Odoo choose the appropriate view
        }

    def action_create_grab_menu_item(self):
        """Create a new Grab menu item for this product"""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': f'Create Grab Menu Item for {self.name}',
            'res_model': 'grab.menu.item',
            'view_mode': 'form',
            'context': {'default_product_id': self.id},
            'target': 'new',
        }

    def action_sync_to_grab_items(self):
        """Sync current product settings to all linked Grab menu items"""
        self.ensure_one()
        if not self.grab_menu_item_ids:
            raise UserError(_("No Grab menu items found for this product."))
        
        for grab_item in self.grab_menu_item_ids:
            grab_item.write({
                'use_grab_price': self.use_grab_price,
                'grab_price': self.grab_price,
                'gst_rate': self.gst_rate,
                'available_status': 'AVAILABLE' if self.grab_available else 'UNAVAILABLE',
            })
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Success'),
                'message': _('Settings synced to %d Grab menu items.') % len(self.grab_menu_item_ids),
                'type': 'success',
            }
        }

    def action_copy_from_grab_item(self):
        """Copy settings from the first Grab menu item to this product"""
        self.ensure_one()
        if not self.grab_menu_item_ids:
            raise UserError(_("No Grab menu items found for this product."))
        
        first_grab_item = self.grab_menu_item_ids[0]
        self.write({
            'use_grab_price': first_grab_item.use_grab_price,
            'grab_price': first_grab_item.grab_price,
            'gst_rate': first_grab_item.gst_rate,
            'grab_available': first_grab_item.available_status == 'AVAILABLE',
        })
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Success'),
                'message': _('Settings copied from Grab menu item: %s') % first_grab_item.name,
                'type': 'success',
            }
        }

    @api.model
    def write(self, vals):
        """Override write to auto-sync changes to Grab menu items if sync is enabled"""
        result = super().write(vals)
        
        # Fields that should trigger sync to Grab items
        sync_fields = ['name', 'list_price', 'use_grab_price', 'grab_price', 'gst_rate', 'grab_available']
        
        if any(field in vals for field in sync_fields):
            for product in self:
                if product.grab_sync_enabled and product.grab_menu_item_ids:
                    # Sync relevant changes to Grab menu items
                    grab_vals = {}
                    if 'use_grab_price' in vals:
                        grab_vals['use_grab_price'] = vals['use_grab_price']
                    if 'grab_price' in vals:
                        grab_vals['grab_price'] = vals['grab_price']
                    if 'gst_rate' in vals:
                        grab_vals['gst_rate'] = vals['gst_rate']
                    if 'grab_available' in vals:
                        grab_vals['available_status'] = 'AVAILABLE' if vals['grab_available'] else 'UNAVAILABLE'
                    
                    if grab_vals:
                        product.grab_menu_item_ids.write(grab_vals)
        
        return result