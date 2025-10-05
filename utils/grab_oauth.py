# your_module/utils/grab_oauth.py
import requests

def grab_get_access_token(client_id, client_secret):
    url = "https://api.grab.com/grabid/v1/oauth2/token"
    headers = {'Content-Type': 'application/x-www-form-urlencoded'}
    data = {
        'grant_type': 'client_credentials',
        'client_id': client_id,
        'client_secret': client_secret,
        'scope': 'food.partner_api'
    }
    resp = requests.post(url, headers=headers, data=data, timeout=10)
    if resp.status_code == 200:
        return resp.json()['access_token']
    else:
        raise Exception(f"Failed to get token: {resp.status_code} {resp.text}")
