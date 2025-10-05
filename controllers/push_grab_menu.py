from odoo import http
from odoo.http import request
from werkzeug.wrappers import Response
import json, logging

_logger = logging.getLogger(__name__)

class GrabPushMenuWebhook(http.Controller):
    @http.route('/grab/webhook/pushGrabMenu', type='http', auth='public', csrf=False, methods=['POST'])
    def push_grab_menu(self, **kw):
        try:
            data = json.loads(request.httprequest.data.decode('utf-8') or '{}')
        except Exception as e:
            _logger.exception("PushGrabMenu invalid json")
            return Response("Bad Request", status=400)

        # 可保存到一张日志表
        request.env['grab.push.menu.log'].sudo().create({
            'grab_merchant_id': data.get('merchantID'),
            'partner_merchant_id': data.get('partnerMerchantID'),
            'payload': json.dumps(data)
        })
        # 如需解析 currency/sellingTimes/categories 可在此入库
        return Response(status=204)
