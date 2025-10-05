from odoo import models, fields, api
import requests

class GrabData(models.Model):
    _name = 'grab.data'
    _description = 'Grab Data'

    name = fields.Char(string='Name')
    menu_item = fields.Char(string='Menu Item')
    price = fields.Float(string='Price')

    def _grab_data_from_api(self):
        client_id = 'cfc0053d52a8452ba249990d6e67a299'
        client_secret = 'UZ2cjZcv_yQa5WZR'
        # 获取 access token（用你之前测通的那段代码）
        token_url = 'https://api.grab.com/grabid/v1/oauth2/token'
        payload = {
            'grant_type': 'client_credentials',
            'client_id': client_id,
            'client_secret': client_secret,
            'scope': 'food.partner_api'
        }
        r = requests.post(token_url, data=payload)
        access_token = r.json().get('access_token')

        # 用 token 拉菜单（把 api_url 换成 Grab 给你的菜单 endpoint）
        api_url = 'https://partner-api.grab.com/food/partner_api/menus'  # 举例，按文档实际为准
        headers = {'Authorization': f'Bearer {access_token}'}
        try:
            response = requests.get(api_url, headers=headers, timeout=10)
            response.raise_for_status()
            data = response.json()
            self.search([]).unlink()
            for item in data.get('menus', []):  # 这里 key 要和返回结构一致
                self.create({
                    'name': item.get('name', ''),
                    'menu_item': item.get('menu_item', ''),
                    'price': item.get('price', 0.0),
                })
            return True
        except Exception as e:
            print(f"Error fetching Grab API: {e}")
            return False
