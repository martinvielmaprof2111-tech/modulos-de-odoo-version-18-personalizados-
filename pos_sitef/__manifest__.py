# -*- coding: utf-8 -*-
{
    'name': 'POS SITEF Pay Integration',
    'version': '18.0.1.0',
    'category': 'Sales/Point of Sale',
    'summary': 'Integración nativa de Pasarela SITEF para Farmaballenas',
    'description': """
        Módulo de integración directa con la pasarela SITEF para el Punto de Venta de Odoo 18.0.
    """,
    'author': 'Martin Vielma',
    'depends': [
        'point_of_sale', 
        'web'
    ],
    'data': [
        'views/payment_method_view.xml',
        'views/pos_config_view.xml',
        'views/pos_sitef_device_view.xml',
    ],
    'assets': {
        'point_of_sale._assets_pos': [
            'pos_sitef_pay/static/src/css/sitef.css',
            'pos_sitef_pay/static/src/js/sitef_auth_service.js',  # ¡Cargado primero para que exista el alias!
            'pos_sitef_pay/static/src/js/sitef_service.js',       # Depende de auth_service
            'pos_sitef_pay/static/src/js/payment_sitef.js',
            'pos_sitef_pay/static/src/js/sitef_validator.js',
        ],
    },
    'installable': True,
    'auto_install': False,
    'license': 'LGPL-3',
}