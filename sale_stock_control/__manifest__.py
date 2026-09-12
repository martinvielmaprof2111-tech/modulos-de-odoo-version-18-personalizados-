{
    'name': 'Sale Stock Control',
    'version': '18.0.1.0.0',
    'depends': [
        'sale',
        'stock',
        'sale_stock',
     
    ],
    'data': [
        'views/sale_order_views.xml',
        'views/stock_location_views.xml',
    ],
    'installable': True,
    'application': False,
}