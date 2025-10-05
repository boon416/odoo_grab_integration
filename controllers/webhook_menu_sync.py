from odoo import http
from odoo.http import request

class GrabMenuWebhookController(http.Controller):

    @http.route('/grab/webhook/menu-sync-state', type='json', auth='public', csrf=False, methods=['POST'])
    def webhook_menu_sync_state(self, **kwargs):
        data = request.jsonrequest
        # 记录同步状态、jobID、status、errors
        # 可以存表，也可以直接_log
        request.env['grab.menu.sync.log'].sudo().create({
            'request_id': data.get('requestID'),
            'merchant_id': data.get('merchantID'),
            'partner_merchant_id': data.get('partnerMerchantID'),
            'job_id': data.get('jobID'),
            'updated_at': data.get('updatedAt'),
            'status': data.get('status'),
            'error': '\n'.join(data.get('errors', [])) if data.get('errors') else None
        })
        return http.Response(status=200)
