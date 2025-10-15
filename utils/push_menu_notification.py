# utils/push_menu_notification.py
# -*- coding: utf-8 -*-
import requests
from .grab_oauth import grab_get_access_token

def push_menu_notification(env, merchant_id: str):
    ICP = env['ir.config_parameter'].sudo()
    # 固定为 /grabfood/partner 这一级
    base = ICP.get_param('grab.partner_api_base', 'https://partner-api.grab.com/grabfood/partner')
    url = f"{base}/v1/merchant/menu/notification"

    token = grab_get_access_token(env)
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    payload = {"merchantID": merchant_id}
    r = requests.post(url, json=payload, headers=headers, timeout=20)
    return r.status_code, (r.text or "")
