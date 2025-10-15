# controllers/grab_api.py
# -*- coding: utf-8 -*-
from functools import wraps
from odoo import http
from odoo.http import request
import json, time, secrets

# ====== 配置与工具 ======
TOKEN_TTL = 7 * 24 * 60 * 60  # 7天

def _get(k, default=None):
    return request.env['ir.config_parameter'].sudo().get_param(k, default)

def _set(k, v):
    request.env['ir.config_parameter'].sudo().set_param(k, v)

# 受保护 webhook 的 Bearer 校验装饰器（Grab 调你其它接口时用）
def require_partner_bearer(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        auth = request.httprequest.headers.get('Authorization', '')
        if not auth.startswith('Bearer '):
            return http.Response(status=401)
        token = auth[7:].strip()

        saved_token = _get('partner.oauth.token')
        exp = int(_get('partner.oauth.token_exp') or 0)
        if not saved_token or token != saved_token or exp <= int(time.time()):
            return http.Response(status=401)
        return fn(*args, **kwargs)
    return wrapper

# ====== Grab 来你这边获取 Partner Access Token ======
class GrabPartnerTokenController(http.Controller):

    @http.route('/grab/oauth/token', type='json', auth='none', methods=['POST'], csrf=False)
    def grab_partner_token(self, **payload):
        """
        接收 JSON:
        {
          "client_id": "<partner.oauth.client_id>",
          "client_secret": "<partner.oauth.client_secret>",
          "grant_type": "client_credentials",
          "scope": "food.partner_api"   # 可选
        }
        返回:
        {
          "access_token": "...",
          "token_type": "Bearer",
          "expires_in": 604799
        }
        """
        cid  = payload.get('client_id')
        csec = payload.get('client_secret')
        grant = payload.get('grant_type')
        scope = payload.get('scope')  # 可选

        exp_cid = _get('partner.oauth.client_id')
        exp_sec = _get('partner.oauth.client_secret')

        # 基础校验
        if grant != 'client_credentials' or not cid or not csec:
            return http.Response(
                status=400, content_type='application/json',
                response=json.dumps({"error": "invalid_request"})
            )

        # 凭证校验
        if cid != exp_cid or csec != exp_sec:
            return http.Response(
                status=401, content_type='application/json',
                response=json.dumps({"error": "invalid_client", "error_description": "Client authentication failed"})
            )

        # scope（若传了就要求正确）
        if scope and scope != 'food.partner_api':
            return http.Response(
                status=400, content_type='application/json',
                response=json.dumps({"error": "invalid_scope"})
            )

        # 复用未过期 token
        now = int(time.time())
        saved_tok = _get('partner.oauth.token')
        saved_exp = int(_get('partner.oauth.token_exp') or 0)
        if saved_tok and saved_exp - now > 60:
            return {
                "access_token": saved_tok,
                "token_type": "Bearer",
                "expires_in": saved_exp - now
            }

        # 生成新 token（不透明字符串；如需 JWT 可自行替换）
        new_tok = secrets.token_urlsafe(64)
        new_exp = now + TOKEN_TTL
        _set('partner.oauth.token', new_tok)
        _set('partner.oauth.token_exp', str(new_exp))

        return {
            "access_token": new_tok,
            "token_type": "Bearer",
            "expires_in": TOKEN_TTL
        }

# ====== 示例：需要 Bearer 的 webhook（给 Grab 调用）======
class GrabWebhooks(http.Controller):

    @http.route('/grab/webhook/get_menu', type='json', auth='none', csrf=False, methods=['POST'])
    @require_partner_bearer
    def get_menu(self, **kwargs):
        # TODO: 返回你真实的菜单
        return {"menu": []}
