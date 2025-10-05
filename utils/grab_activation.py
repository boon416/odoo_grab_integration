# odoo_grab_integration/utils/grab_activation.py
import logging
import requests

_logger = logging.getLogger(__name__)

DEFAULT_BASE = 'https://partner-api.grab.com/grabfood'
ACTIVATION_PATH = 'partner/v1/self-serve/activation'

def _normalize_base(base: str) -> str:
    """
    清洗 base，去掉多余的 / 与末尾 /partner，避免 /partner/partner 重复。
    """
    base = (base or DEFAULT_BASE).strip()
    base = base.rstrip('/')
    if base.endswith('/partner'):
        base = base[:-len('/partner')]
    return base

def create_self_serve_activation(partner_merchant_id: str, access_token: str, base: str = DEFAULT_BASE) -> dict:
    """
    调用 Grab Activation API，返回 JSON：
      {"activationUrl": "..."}
    """
    base = _normalize_base(base)
    url = f"{base}/{ACTIVATION_PATH}"

    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json",
    }
    payload = {"partner": {"merchantID": partner_merchant_id}}

    _logger.info("[Grab] Activation request -> %s, payload=%s", url, payload)
    r = requests.post(url, json=payload, headers=headers, timeout=15)
    _logger.info("[Grab] Activation response <- status=%s, body=%s", r.status_code, r.text)

    # 非 2xx 抛错（上层会拦截并转成友好提示）
    r.raise_for_status()
    return r.json()
