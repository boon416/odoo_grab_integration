from odoo import models, fields

class GrabPushMenuLog(models.Model):
    _name = 'grab.push.menu.log'
    _description = 'Grab Push Menu Webhook Payload'
    grab_merchant_id = fields.Char()
    partner_merchant_id = fields.Char()
    payload = fields.Text()
