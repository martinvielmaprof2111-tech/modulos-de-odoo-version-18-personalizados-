from odoo import fields, models, api, _
from odoo.exceptions import UserError


class AccountMove(models.Model):
    _inherit = 'account.move'

    def action_post(self):
        """Al publicar la factura de cliente, verifica si excede el límite de crédito en USD."""
        for move in self:
            if move.is_sale_document() and move.partner_id:
                amount_company = move.currency_id._convert(
                    move.amount_total,
                    move.company_id.currency_id,
                    move.company_id,
                    move.date or fields.Date.today(),
                )

                msg, exceeded = move.partner_id._build_credit_warning_message_usd(
                    move, current_amount_company=amount_company
                )

                if exceeded:
                    raise UserError(_("No se puede publicar la factura.\n\n%s", msg))

        return super(AccountMove, self).action_post()


class AccountMoveLine(models.Model):
    _inherit = 'account.move.line'

    @api.onchange('amount_currency', 'debit', 'credit')
    def _check_amount_currency_sign_sync(self):
        for line in self:
            balance = line.debit - line.credit
            if balance != 0 and line.amount_currency != 0:
                if (balance > 0 and line.amount_currency < 0) or (balance < 0 and line.amount_currency > 0):
                    line.amount_currency = -line.amount_currency

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            debit = vals.get('debit', 0.0)
            credit = vals.get('credit', 0.0)
            balance = debit - credit
            amount_currency = vals.get('amount_currency', 0.0)

            if balance != 0 and amount_currency != 0:
                if (balance > 0 and amount_currency < 0) or (balance < 0 and amount_currency > 0):
                    vals['amount_currency'] = abs(amount_currency) if balance > 0 else -abs(amount_currency)

        return super().create(vals_list)