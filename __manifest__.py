{
    'name': 'Grab Dashboard',
    'version': '1.0.0',
    'summary': 'Integrate and display Grab data in Odoo dashboard (Odoo 18 ready)',
    'author': 'Boon',
    'depends': ['base', 'product', 'website_sale'],
    'data': [
        'security/ir.model.access.csv',
        'views/order_ready_time_wizard.xml',
        'views/grab_view.xml',
        'views/grab_menu_views.xml',
    ],
    'installable': True,
    'application': True,
    'license': 'LGPL-3',
    'assets': {},
}
