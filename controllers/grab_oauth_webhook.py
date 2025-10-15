# controllers/grab_oauth_webhook.py
from odoo import http
from odoo.http import request
import base64, time, requests

GRAB_IDP = "https://api.grab.com/grabid/v1/oauth2/token"
SCOPE = "food.partner_api"

def _get(k, default=""):
    return request.env['ir.config_parameter'].sudo().get_param(k, default)
def _set(k, v):
    return request.env['ir.config_parameter'].sudo().set_param(k, v)

class GrabOAuthWebhook(http.Controller):
    @http.route('/api/grab/oauth/token', type='json', auth='public', methods=['POST'], csrf=False)
    def issue_token(self, **payload):
        # 1) 校验 Basic Auth
        auth = request.httprequest.headers.get('Authorization', '')
        if not auth.startswith('Basic '):
            return http.Response(status=401)

        try:
            raw = base64.b64decode(auth.split(' ', 1)[1]).decode('utf-8')
            cid, csec = raw.split(':', 1)
        except Exception:
            return http.Response(status=401)

        exp_cid  = _get('partner.oauth.client_id')
        exp_sec  = _get('partner.oauth.client_secret')
        if cid != exp_cid or csec != exp_sec:
            return http.Response(status=401)

        # 2) 返回缓存 token（未过期就复用）
        tok = _get('grab.oauth.access_token')
        exp = float(_get('grab.oauth.expires_at', '0') or 0)
        now = time.time()
        if tok and now < exp - 60:
            return {
                "access_token": tok,
                "token_type": "Bearer",
                "expires_in": max(0, int(exp - now))
            }

        # 3) 代表伙伴去 Grab IDP 换新 token
        resp = requests.post(GRAB_IDP, json={
            "client_id": _get('grab.oauth.client_id'),
            "client_secret": _get('grab.oauth.client_secret'),
            "grant_type": "client_credentials",
            "scope": SCOPE
        }, timeout=10)
        resp.raise_for_status()
        data = resp.json()

        ttl = int(data.get("expires_in", 0))
        _set('grab.oauth.access_token', data.get("access_token", ""))
        _set('grab.oauth.expires_at', str(now + ttl))

        return data
