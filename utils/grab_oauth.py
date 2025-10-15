# utils/grab_oauth.py
# -*- coding: utf-8 -*-
import time
import requests

def grab_get_access_token(env):
    ICP = env['ir.config_parameter'].sudo()
    cid  = ICP.get_param('grab.client_id')
    csec = ICP.get_param('grab.client_secret')

    tok  = ICP.get_param('grab.oauth.token')
    exp  = int(ICP.get_param('grab.oauth.token_exp') or 0)
    now  = int(time.time())
    if tok and exp - now > 60:
        return tok

    token_url = ICP.get_param('grab.oauth.token_url') or 'https://api.grab.com/grabid/v1/oauth2/token'
    payload = {
        "client_id": cid,
        "client_secret": csec,
        "grant_type": "client_credentials",
        "scope": "food.partner_api",
    }
    r = requests.post(token_url, json=payload, headers={'Content-Type': 'application/json'}, timeout=20)
    # 若授权失败，清缓存，抛错更清晰
    if r.status_code == 401:
        ICP.set_param('grab.oauth.token', '')
        ICP.set_param('grab.oauth.token_exp', '0')
    r.raise_for_status()
    data = r.json()
    tok = data['access_token']
    ttl = int(data.get('expires_in', 604799))
    ICP.set_param('grab.oauth.token', tok)
    ICP.set_param('grab.oauth.token_exp', str(now + ttl))
    return tok
