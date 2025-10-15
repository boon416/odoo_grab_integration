from odoo import models, fields, api


class GrabPriceWizard(models.TransientModel):
    _name = 'grab.price.wizard'
    _description = 'Grab Price Management Wizard'

    item_ids = fields.Many2many('grab.menu.item', string='Menu Items')
    markup_percentage = fields.Float(string='Markup Percentage (%)', default=20.0,
                                    help='Percentage to add to product price for platform fees')
    gst_rate = fields.Float(string='GST Rate (%)', default=7.0,
                           help='GST rate to apply (default 7% for Singapore)')
    price_strategy = fields.Selection([
        ('copy', 'Copy Product Price (1:1)'),
        ('markup', 'Add Markup Percentage'),
        ('custom', 'Set Custom Base Price'),
    ], default='markup', string='Pricing Strategy')
    custom_base_price = fields.Float(string='Custom Base Price',
                                    help='Base price to use for all selected items')

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        if self.env.context.get('active_model') == 'grab.menu.item':
            res['item_ids'] = [(6, 0, self.env.context.get('active_ids', []))]
        return res

    def action_apply_prices(self):
        """Apply the selected pricing strategy to all selected items"""
        for item in self.item_ids:
            if not item.product_id:
                continue
                
            if self.price_strategy == 'copy':
                # Copy product price directly
                item.grab_price = item.product_id.list_price
            elif self.price_strategy == 'markup':
                # Apply markup percentage
                base_price = item.product_id.list_price
                markup_amount = base_price * (self.markup_percentage / 100.0)
                item.grab_price = base_price + markup_amount
            elif self.price_strategy == 'custom':
                # Use custom base price
                item.grab_price = self.custom_base_price
            
            # Update GST rate and enable Grab pricing
            item.gst_rate = self.gst_rate
            item.use_grab_price = True

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Prices Updated',
                'message': f'Successfully updated Grab prices for {len(self.item_ids)} items',
                'type': 'success',
            }
        }

    def action_preview_prices(self):
        """Preview the calculated prices before applying"""
        preview_data = []
        for item in self.item_ids:
            if not item.product_id:
                continue
                
            current_price = item.product_id.list_price
            
            if self.price_strategy == 'copy':
                new_grab_price = current_price
            elif self.price_strategy == 'markup':
                markup_amount = current_price * (self.markup_percentage / 100.0)
                new_grab_price = current_price + markup_amount
            elif self.price_strategy == 'custom':
                new_grab_price = self.custom_base_price
            else:
                new_grab_price = current_price
            
            # Calculate price with GST
            gst_amount = new_grab_price * (self.gst_rate / 100.0)
            final_price = new_grab_price + gst_amount
            
            preview_data.append({
                'item_name': item.name,
                'current_price': current_price,
                'new_grab_price': new_grab_price,
                'gst_amount': gst_amount,
                'final_price': final_price,
            })

        return {
            'type': 'ir.actions.act_window',
            'name': 'Price Preview',
            'res_model': 'grab.price.preview',
            'view_mode': 'tree',
            'target': 'new',
            'context': {
                'default_preview_data': preview_data,
                'default_wizard_id': self.id,
            }
        }


class GrabPricePreview(models.TransientModel):
    _name = 'grab.price.preview'
    _description = 'Grab Price Preview'

    wizard_id = fields.Many2one('grab.price.wizard', string='Wizard')
    item_name = fields.Char(string='Item Name')
    current_price = fields.Float(string='Current Price')
    new_grab_price = fields.Float(string='New Grab Price (Excl. GST)')
    gst_amount = fields.Float(string='GST Amount')
    final_price = fields.Float(string='Final Price (Incl. GST)')