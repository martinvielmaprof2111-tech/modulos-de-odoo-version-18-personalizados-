from odoo import models, fields


class StockLocation(models.Model):
    _inherit = 'stock.location'

    allow_sale_stock = fields.Boolean(
        string='Disponible para Ventas',
        default=False,
        help='Si está activo, el stock en esta ubicación se incluirá en el cálculo de stock disponible para Ventas.'
    )