{
    'name': 'Resumen de Vencimiento CxC Custom',
    'version': '18.0.1.0.0',
    'category': 'Accounting/Accounting',
    'summary': 'Informe de Análisis de Vencimiento de Cuentas por Cobrar agrupado por Vendedor y Cliente.',
    'depends': [
        'account',
        'web',
    ],
    'data': [
        'security/ir.model.access.csv',
        'views/aged_receivable_wizard_view.xml',
        'report/aged_receivable_report.xml',
    ],
    'installable': True,
    'application': False,
    'license': 'LGPL-3',
}