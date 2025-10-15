# -*- coding: utf-8 -*-
from odoo import http
from odoo.http import request
import logging, json, re

_logger = logging.getLogger(__name__)

class GrabMenuController(http.Controller):

    @http.route('/grab/menu/export', type='json', auth='none', methods=['POST'], csrf=False)
    def grab_menu_export(self, **kwargs):
        # 记录 requestId 用于和 Grab 对账
        rid = request.httprequest.headers.get('X-Request-Id') \
              or request.httprequest.headers.get('X-Correlation-Id')

        # ---- 鉴权：仅要求带 Bearer，不和本地系统参数比对 ----
        auth = (request.httprequest.headers.get('Authorization')
                or request.httprequest.headers.get('authorization') or '').strip()
        m = re.match(r'(?i)Bearer\s+(.+)', auth)
        has_bearer = bool(m and m.group(1).strip())

        # 可通过系统参数打开调试日志（不会打印令牌内容）
        if request.env['ir.config_parameter'].sudo().get_param('grab.debug_export_auth') == '1':
            _logger.info('[/grab/menu/export] rid=%s Authorization header present=%s', rid, has_bearer)

        # 若你想在联调阶段更宽松，允许“没有 Bearer 也放行”，把下面两行注释掉
        if not has_bearer:
            return request.make_json_response({'error': 'unauthorized', 'rid': rid}, status=401)

        # ---- 读取 body：允许为空；若无 merchantId，则取第一条菜单 ----
        body = {}
        try:
            body = request.jsonrequest or {}
        except Exception:
            body = {}

        merchant_id = (body.get('merchantId')
                        or body.get('merchant_id')
                        or request.params.get('merchantId')
                        or request.params.get('merchant_id'))

        domain = [('merchant_id', '=', merchant_id)] if merchant_id else []
        menu = request.env['grab.menu'].sudo().search(domain, limit=1)
        if not menu:
            return request.make_json_response({'error': 'menu_not_found', 'rid': rid}, status=404)

        try:
            payload = menu.build_export_payload()
            # 尽量少打日志，避免 payload 过大；只记录大小
            _logger.info('[/grab/menu/export] rid=%s merchant=%s bytes=%s',
                         rid, menu.merchant_id, len(json.dumps(payload)))
            return payload
        except Exception as e:
            _logger.exception('[/grab/menu/export] rid=%s failed: %s', rid, e)
            return request.make_json_response({'error': 'internal_error', 'rid': rid}, status=500)
