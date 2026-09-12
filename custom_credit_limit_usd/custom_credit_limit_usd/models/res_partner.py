from odoo import fields, models, _
from odoo.tools import format_amount


class ResPartner(models.Model):
    _inherit = 'res.partner'

    def _get_credit_limit_in_usd(self, company):
        """Obtiene el límite en USD considerando la prioridad."""
        self.ensure_one()
        usd_currency = self.env.ref('base.USD')
        company_currency = company.currency_id

        # Prioridad 1: Límite específico en el cliente (convertido de Bs. a USD)
        if self.use_partner_credit_limit and self.credit_limit > 0:
            return company_currency._convert(
                self.credit_limit,
                usd_currency,
                company,
                fields.Date.today(),
            )

        # Prioridad 2: Límite predeterminado global en USD desde Ajustes
        return float(
            self.env['ir.config_parameter']
            .sudo()
            .get_param('custom_credit_limit_usd.credit_limit_usd_default', 0.0)
        )

    def _build_credit_warning_message_usd(self, record, current_amount_company=0.0):
        """Construye el texto del mensaje de alerta en USD."""
        self.ensure_one()
        company = record.company_id
        usd_currency = self.env.ref('base.USD')
        company_currency = company.currency_id

        limit_usd = self._get_credit_limit_in_usd(company)
        if limit_usd <= 0:
            return "", False

        # Deuda actual + monto del documento actual en la moneda base
        total_due_company = self.credit + current_amount_company
        
        # Conversión a USD según la tasa del día
        total_due_usd = company_currency._convert(
            total_due_company,
            usd_currency,
            company,
            fields.Date.today(),
        )

        if total_due_usd > limit_usd:
            msg = _(
                "%(partner_name)s llegó al límite de crédito de: %(limit)s.\n"
                "Cantidad total debida (incluyendo este documento): %(total_due)s.",
                partner_name=self.name,
                limit=format_amount(self.env, limit_usd, usd_currency),
                total_due=format_amount(self.env, total_due_usd, usd_currency),
            )
            return msg, True

        return "", False