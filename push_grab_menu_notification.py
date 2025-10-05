from .utils.grab_oauth import grab_get_access_token
import requests

def push_grab_menu_notification(merchant_id, client_id, client_secret):
    access_token = grab_get_access_token(client_id, client_secret)
    url = 'https://partner-api.grab.com/grabfood/partner/v1/merchant/menu/notification'
    headers = {
        'Authorization': f'Bearer {access_token}',
        'Content-Type': 'application/json'
    }
    data = {
        "merchantID": merchant_id
    }
    resp = requests.post(url, headers=headers, json=data, timeout=10)
    return resp.status_code, resp.text
