from odoo import api, fields, models, _
from odoo.exceptions import UserError
from ..utils.push_grab_new_order_ready_time import push_grab_new_order_ready_time

class GrabOrderReadyTimeWizard(models.TransientModel):
    _name = 'grab.order.ready.time.wizard'
    _description = 'Update Grab Order Ready Time'

    order_id = fields.Many2one('grab.order', string='Order', required=True)
    new_order_ready_time = fields.Datetime(string='New Ready Time', required=True, default=lambda self: fields.Datetime.now())

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        active_id = self.env.context.get('active_id')
        if active_id and 'order_id' in fields_list:
            res['order_id'] = active_id
        return res

    def action_update_ready_time(self):
        self.ensure_one()
        order = self.order_id
        if not order:
            raise UserError(_("No order selected."))

        ICP = self.env['ir.config_parameter'].sudo()
        client_id = ICP.get_param('grab.client_id')
        client_secret = ICP.get_param('grab.client_secret')
        if not (client_id and client_secret):
            raise UserError(_("Missing Grab API credentials (grab.client_id / grab.client_secret)."))

        # 如果你的工具函数在 utils/ 下，用下面这一行（注意两点）
        # 1) utils 目录需要有 __init__.py
        # 2) 相对导入是从当前模块包往上一级再进 utils
        from ..utils.push_grab_new_order_ready_time import push_grab_new_order_ready_time

        status, text = push_grab_new_order_ready_time(
            order_id=order.grab_order_id,
            new_order_ready_time=fields.Datetime.to_string(self.new_order_ready_time),
            client_id=client_id,
            client_secret=client_secret,
        )
        if status not in (200, 201, 202):
            raise UserError(_("Grab API failed: %s %s") % (status, text))

        order.sudo().write({'scheduled_time': self.new_order_ready_time})
        return {'type': 'ir.actions.act_window_close'}
