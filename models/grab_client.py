# models/grab_client.py
import time, requests
from odoo import models, api, _
from odoo.exceptions import UserError

TOKEN_PARAM = "grab.oauth.token"
EXP_PARAM   = "grab.oauth.token_exp"

class GrabApiClient(models.AbstractModel):
    _name = 'grab.api.client'
    _description = 'Grab API Client (OAuth & Calls)'

    def _get_params(self):
        icp = self.env['ir.config_parameter'].sudo()
        cid = icp.get_param('grab.client_id')
        csec = icp.get_param('grab.client_secret')
        scope = icp.get_param('grab.scope', 'food.partner_api')
        if not cid or not csec:
            raise UserError(_("Missing Grab client_id/client_secret in System Parameters."))
        return cid, csec, scope, icp

    def get_access_token(self):
        cid, csec, scope, icp = self._get_params()
        now = int(time.time())
        token = icp.get_param(TOKEN_PARAM)
        exp   = icp.get_param(EXP_PARAM)
        if token and exp and now < int(exp) - 300:
            return token

        url = "https://api.grab.com/grabid/v1/oauth2/token"
        payload = {"grant_type":"client_credentials","client_id":cid,"client_secret":csec,"scope":scope}
        r = requests.post(url, json=payload, timeout=15); r.raise_for_status()
        data = r.json() or {}
        token = data.get("access_token"); ttl = int(data.get("expires_in") or 0)
        if not token or not ttl:
            raise UserError(_("Grab OAuth response missing token/expires_in: %s") % data)
        icp.set_param(TOKEN_PARAM, token); icp.set_param(EXP_PARAM, str(now + ttl))
        return token
