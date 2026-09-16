# -*- coding: utf-8 -*-
{
    'name': 'Número de Control Fiscal por Sucursal y Diario',
    'version': '18.0.1.0.0',
    'category': 'Accounting/Localizations',
    'summary': 'Gestión del correlativo de número de control fiscal por sucursal y diario con asignación automática.',
    'depends': ['account'],
    'data': [
        'security/ir.model.access.csv',
        'security/ir_rule.xml',
        'views/invoice_control_sequence_views.xml',
        'views/account_move_views.xml',
    ],
    'post_init_hook': 'post_init_hook',
    'installable': True,
    'application': False,
    'license': 'LGPL-3',
}