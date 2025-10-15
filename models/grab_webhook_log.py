# File: odoo_grab_integration/models/grab_webhook_log.py
# -*- coding: utf-8 -*-
from odoo import models, fields

class GrabWebhookLog(models.Model):
    _name = "grab.webhook.log"
    _description = "Grab Webhook Raw Log"
    _order = "create_date desc"

    event_type = fields.Selection([
        ("order_submit", "Order Submit"),
        ("order_state", "Order State"),
    ], required=True)
    raw_json = fields.Text()
