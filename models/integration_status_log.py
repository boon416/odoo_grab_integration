from odoo import models, fields

class GrabIntegrationStatusLog(models.Model):
    _name = 'grab.integration.status.log'
    _description = 'Grab Integration Status Webhook Log'
    grab_merchant_id = fields.Char()
    partner_merchant_id = fields.Char()
    status = fields.Char()
    payload = fields.Text()
