{
    'name': 'Integración iCompras360',
    'version': '18.0.1.1.0',
    'category': 'Inventory/Inventory',
    'summary': 'Módulo para la exportación de inventario e importación interactiva de pedidos desde iCompras360.',
    'description': """
        Módulo de integración con iCompras360.
        Permite la exportación automatizada de inventarios y añade un asistente interactivo 
        con rango de fechas para consultar e inyectar pedidos sugeridos como órdenes de compra en Odoo.
    """,
    'author': 'Martin Vielma',
    'website': 'https://www.pgconsultores.com',
    'depends': [
        'base',
        'product',
        'stock',
        'purchase',
    ],
    'data': [
        'security/ir.model.access.csv',
        'views/icompras_config_exportador_views.xml',
        'views/icompras_config_importador_views.xml',
        'wizards/icompras_import_wizard_views.xml',
    ],
    'installable': True,
    'application': True,
    'license': 'LGPL-3',
}