from .utils.grab_oauth import grab_get_access_token
import requests

def push_grab_order_ready(order_id, client_id, client_secret, mark_status=1):
    """
    Push order ready/completed to Grab.
    mark_status:
        1 - Mark as ready
        2 - Mark as completed (dine-in only)
    """
    access_token = grab_get_access_token(client_id, client_secret)
    url = 'https://partner-api.grab.com/grabfood/partner/v1/orders/mark'
    headers = {
        'Authorization': f'Bearer {access_token}',
        'Content-Type': 'application/json'
    }
    data = {
        "orderID": order_id,
        "markStatus": mark_status
    }
    resp = requests.post(url, headers=headers, json=data, timeout=10)
    return resp.status_code, resp.text
