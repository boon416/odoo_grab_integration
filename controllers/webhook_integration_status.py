from odoo import http
from odoo.http import request
from werkzeug.wrappers import Response
import json, logging

_logger = logging.getLogger(__name__)

class GrabWebhookIntegrationStatus(http.Controller):
    @http.route('/grab/webhook/integration_status', type='http', auth='public', csrf=False, methods=['POST'])
    def integration_status_webhook(self, **kw):
        try:
            data = json.loads(request.httprequest.data.decode('utf-8') or '{}')
        except Exception:
            return Response(status=400)

        # 入库或更新状态
        request.env['grab.integration.status.log'].sudo().create({
            'grab_merchant_id': data.get('grabMerchantID') or data.get('merchantID'),
            'partner_merchant_id': data.get('partnerMerchantID'),
            'status': data.get('integrationStatus') or data.get('status'),
            'payload': json.dumps(data)
        })
        return Response(status=204)
