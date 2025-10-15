# controllers/webhook_menu_sync.py
# -*- coding: utf-8 -*-
from odoo import http
from odoo.http import request
import json
import logging

_logger = logging.getLogger(__name__)

def _json_body():
    """稳妥地从 HTTP body 取 JSON（不依赖 request.jsonrequest）。"""
    try:
        raw = request.httprequest.data or b""
        return json.loads(raw.decode("utf-8")) if raw else {}
    except Exception as e:
        _logger.warning("Grab webhook: invalid JSON body: %s", e)
        return {}

def _parse_grab_ts(s):
    """
    把 Grab 的 RFC3339 时间（如 2025-10-07T10:11:19.629454814Z）
    转成 Odoo Datetime 可接受的字符串：YYYY-MM-DD HH:MM:SS（UTC）。
    """
    if not s or not isinstance(s, str):
        return False
    try:
        # 去掉尾部 Z（UTC），砍掉小数秒，替换 T 空格
        if s.endswith("Z"):
            s = s[:-1]
        if "." in s:
            s = s.split(".", 1)[0]
        s = s.replace("T", " ")
        # 此时形如 2025-10-07 10:11:19
        # Odoo Datetime 字段接受这个格式的字符串（视为服务器时区/UTC）
        return s
    except Exception:
        return False

class GrabMenuWebhookController(http.Controller):

    @http.route('/grab/webhook/menu-sync-state', type='http', auth='public', csrf=False, methods=['POST'])
    def webhook_menu_sync_state(self, **kwargs):
        data = _json_body()

        # 记录原始 payload 方便排错
        _logger.info("Grab Menu Sync Webhook payload: %s", data)

        # 尝试把 updatedAt 转为 Odoo Datetime 可用的字符串；转不动就留空
        updated_at_dt = _parse_grab_ts(data.get('updatedAt'))

        # 兼容不同大小写/命名
        vals = {
            'request_id': data.get('requestID') or data.get('requestId'),
            'merchant_id': data.get('merchantID'),
            'partner_merchant_id': data.get('partnerMerchantID'),
            'job_id': data.get('jobID') or data.get('jobId'),
            # 如果你的模型里 updated_at 是 Datetime 字段，用 parsed；是 Char 就也能直接塞字符串
            'updated_at': updated_at_dt or (data.get('updatedAt') or False),
            'status': data.get('status'),
            'error': '\n'.join(data.get('errors', [])) if data.get('errors') else None,
        }

        try:
            request.env['grab.menu.sync.log'].sudo().create(vals)
        except Exception as e:
            # 一旦模型字段类型冲突（比如 updated_at 真的是 Datetime 而我们传了原始字符串）
            # 降级：去掉 updated_at，再次写入；并把原值写到一个原始字段里（若模型有 Char 字段可考虑加一个）
            _logger.error("Grab Menu Sync Log create failed: %s; vals=%s", e, vals)
            safe_vals = dict(vals)
            safe_vals.pop('updated_at', None)
            # 如果模型没有存原始时间的字段，可以忽略；有的话如下：
            if 'updated_at_raw' in request.env['grab.menu.sync.log']._fields:
                safe_vals['updated_at_raw'] = data.get('updatedAt')
            request.env['grab.menu.sync.log'].sudo().create(safe_vals)

        # 规范：204 No Content
        return request.make_response("", status=204)
