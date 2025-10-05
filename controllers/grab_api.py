from odoo import http
from odoo.http import request
import json, logging

_logger = logging.getLogger(__name__)

class GrabOAuthController(http.Controller):
    @http.route('/grab/oauth/token', type='http', auth='public', methods=['POST'], csrf=False)
    def grab_oauth_token(self, **post):
        # 兼容 application/json 和 x-www-form-urlencoded
        data = request.httprequest.get_json(force=True, silent=True) or request.params or {}

        client_id = data.get('client_id')
        client_secret = data.get('client_secret')
        grant_type = data.get('grant_type')
        scope = data.get('scope')

        # 你自己的校验逻辑
        if (
            client_id == 'cfc0053d52a8452ba249990d6e67a299'
            and client_secret == 'UZ2cjZcv_yQa5WZR'
            and grant_type == 'client_credentials'
            and scope == 'food.partner_api'
        ):
            # 实际生产建议生成JWT或者数据库存token
            access_token = "test_token"
            return http.Response(
                json.dumps({
                    "access_token": access_token,
                    "token_type": "Bearer",
                    "expires_in": 3600
                }),
                status=200,
                mimetype='application/json'
            )
        else:
            return http.Response(
                json.dumps({
                    "error": "invalid_client",
                    "error_description": "Client authentication failed"
                }),
                status=401,
                mimetype='application/json'
            )
