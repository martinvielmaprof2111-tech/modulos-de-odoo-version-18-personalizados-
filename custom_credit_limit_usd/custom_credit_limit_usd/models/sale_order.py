from odoo import fields, models, _
from odoo.exceptions import UserError


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    def _get_partner_credit_warning(self):
        """Muestra el banner amarillo superior en la Cotización/Venta."""
        self.ensure_one()
        if not self.partner_id:
            return ""

        # Total del pedido a moneda de la compañía
        amount_company = self.currency_id._convert(
            self.amount_total,
            self.company_id.currency_id,
            self.company_id,
            self.date_order or fields.Date.today(),
        )

        msg, exceeded = self.partner_id._build_credit_warning_message_usd(
            self, current_amount_company=amount_company
        )
        return msg if exceeded else ""

    def action_confirm(self):
        """Bloquea la confirmación si supera el límite en USD."""
        for order in self:
            warning_msg = order._get_partner_credit_warning()
            if warning_msg:
                raise UserError(_(
                    "No se puede confirmar la Orden de Venta.\n\n%s", warning_msg
                ))
        return super(SaleOrder, self).action_confirm()