from odoo import models, fields

class GrabMenuSyncLog(models.Model):
    _name = 'grab.menu.sync.log'
    _description = 'Grab Menu Sync Log'
    request_id = fields.Char()
    job_id = fields.Char()
    merchant_id = fields.Char()
    partner_merchant_id = fields.Char()
    status = fields.Char()
    updated_at = fields.Datetime()
    error = fields.Text()
