from odoo import models, fields
from odoo.exceptions import UserError
from ..utils.push_grab_new_order_ready_time import push_grab_new_order_ready_time
import logging
import pytz

_logger = logging.getLogger(__name__)

class GrabOrderReadyTimeWizard(models.TransientModel):
    _name = 'grab.order.ready.time.wizard'
    _description = 'Update Grab Order Ready Time'

    order_id = fields.Many2one('grab.order', string='Order', required=True)
    new_order_ready_time = fields.Datetime('New Ready Time', required=True)

    def action_update_ready_time(self):
        self.ensure_one()
        order = self.order_id
        if not order:
            raise UserError("No order selected.")

        client_id = self.env['ir.config_parameter'].sudo().get_param('grab.client_id')
        client_secret = self.env['ir.config_parameter'].sudo().get_param('grab.client_secret')

        value = self.new_order_ready_time
        if not value:
            raise UserError("Please provide the new ready time.")

        # 转 UTC ISO8601 (Z)
        if value.tzinfo:
            value_utc = value.astimezone(pytz.utc)
        else:
            value_utc = pytz.utc.localize(value)
        iso8601_str = value_utc.strftime('%Y-%m-%dT%H:%M:%SZ')

        _logger.info("Pushing new order ready time %s for Grab order %s", iso8601_str, order.grab_order_id)

        status_code, resp_text = push_grab_new_order_ready_time(
            order.grab_order_id, iso8601_str, client_id, client_secret
        )
        if status_code == 204:
            msg = "Ready time updated successfully (204 No Content)"
            level = 'success'
            _logger.info(msg)
        else:
            msg = f"Failed: {status_code} {resp_text}"
            level = 'danger'
            _logger.error(msg)

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Push Ready Time to Grab',
                'message': msg,
                'type': level,
                'sticky': False,
            }
        }
