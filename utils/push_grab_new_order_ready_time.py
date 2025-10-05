from .grab_oauth import grab_get_access_token
import requests

def push_grab_new_order_ready_time(order_id, new_order_ready_time, client_id, client_secret):
    access_token = grab_get_access_token(client_id, client_secret)
    url = 'https://partner-api.grab.com/grabfood/partner/v1/order/readytime'
    headers = {
        'Authorization': f'Bearer {access_token}',
        'Content-Type': 'application/json'
    }
    data = {
        "orderID": order_id,
        "newOrderReadyTime": new_order_ready_time  # 必须是 ISO8601 格式字符串
    }
    resp = requests.put(url, headers=headers, json=data, timeout=10)
    return resp.status_code, resp.text
