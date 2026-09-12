    {
    'name': 'Límite de Crédito en USD',
    'version': '18.0.1.0.0',
    'category': 'Sales/Accounting',
    'summary': 'Adapta la verificación y el mensaje del límite de crédito a dólares (USD).',
    'depends': ['account', 'sale'],
    'data': [
        'views/res_config_settings_views.xml',
        'views/stock_picking_views.xml',
    ],
    'installable': True,
    'license': 'LGPL-3',
}