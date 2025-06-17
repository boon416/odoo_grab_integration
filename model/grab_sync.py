from odoo import models, fields, api
from grabfood import GrabFoodAPI

class GrabIntegration(models.Model):
    _name = 'grab.integration'
    _description = 'Grab Integration Test'

    name = fields.Char(string='Test Name', default='Grab API Connection')

    def action_test_grab_connection(self):
        # 这里填你的Grab账号和密码
        email = 'your_grab_email'
        password = 'your_grab_password'
        try:
            api = GrabFoodAPI(email=email, password=password)
            stores = api.get_stores()
            # 打印到Odoo日志
            _logger = self.env['ir.logging']
            print(f"Grab stores: {stores}")
            return True
        except Exception as e:
            print(f"Grab connection error: {e}")
            return False
