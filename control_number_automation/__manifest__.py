{
    'name': 'Automatización de Número de Control de Facturas',
    'version': '18.0.1.0.0',
    'category': 'Accounting',
    'summary': 'Generación automática y control de secuencias para el campo nro_ctrl en facturas.',
    'author': 'Tu Nombre / Empresa',
    'website': 'https://www.tuempresa.com',
    'depends': [
        'account',
    ],
    'data': [
        'security/ir.model.access.csv',
        'views/control_number_seq_views.xml',
        'views/account_move_views.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
    'license': 'LGPL-3',
}