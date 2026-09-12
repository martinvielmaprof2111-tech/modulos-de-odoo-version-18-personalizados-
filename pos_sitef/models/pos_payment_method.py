# -*- coding: utf-8 -*-
from odoo import fields, models

class PosPaymentMethod(models.Model):
    _inherit = 'pos.payment.method'

    use_pasarela_sitef = fields.Boolean(string='¿Usar pasarela SITEF?', default=False)
    tipo_servicio_sitef = fields.Selection([
        ('pago_movil', 'Pago Móvil (Consulta)'),
        ('vuelto', 'Vuelto (Emisión)'),
        ('pos_terminal', 'Punto de Venta (Terminal)')
    ], string='Tipo de Servicio SITEF', default='pago_movil')

    # ESTO ES LO QUE HACE QUE APAREZCA EN EL COMBOBOX DEL POS
    def _get_payment_terminal_selection(self):
        res = super()._get_payment_terminal_selection()
        res.append(('payment_sitef', 'SITEF Banesco'))
        return res