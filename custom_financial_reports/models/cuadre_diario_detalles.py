from odoo import models, fields

class CuadreDiarioDetalles(models.TransientModel):
    _name = 'cuadre.diario.detalles'
    _description = 'Wizard Cuadre Diario Detalles'

    company_id = fields.Many2one('res.company', string='Empresa/Sucursal', default=lambda self: self.env.company, required=True)
    date_from = fields.Date(string='Desde', required=True, default=fields.Date.context_today)
    date_to = fields.Date(string='Hasta', required=True, default=fields.Date.context_today)

    def action_print_pdf(self):
        return self.env.ref('custom_financial_reports.action_report_cuadre_diario_detalles').report_action(self)


class ReportCuadreDiarioDetalles(models.AbstractModel):
    _name = 'report.custom_financial_reports.template_cuadre_diario_detalles'
    _description = 'Reporte QWeb Cuadre Diario Detalles'

    def _get_report_values(self, docids, data=None):
        docs = self.env['cuadre.diario.detalles'].browse(docids)
        company = docs.company_id
        date_from = docs.date_from
        date_to = docs.date_to

        currency_usd = self.env.ref('base.USD', raise_if_not_found=False) or self.env['res.currency'].search([('name', '=', 'USD')], limit=1)

        def get_amount_usd(amount, from_currency, date):
            if not currency_usd or not amount:
                return 0.0
            if from_currency == currency_usd:
                return amount
            return from_currency._convert(amount, currency_usd, company, date or fields.Date.today())

        # Búsqueda con sudo() para omitir bloqueo de permisos entre empresas
        invoices = self.env['account.move'].sudo().search([
            ('invoice_date', '>=', date_from),
            ('invoice_date', '<=', date_to),
            ('company_id', '=', company.id),
            ('move_type', 'in', ['out_invoice', 'out_refund']),
            ('state', 'in', ['posted', 'cancel']),
        ], order='invoice_date asc, name asc')

        invoice_details = []
        grand_total_facturado = 0.0
        grand_total_facturado_usd = 0.0
        grand_total_pagado = 0.0
        grand_total_pagado_usd = 0.0

        for inv in invoices:
            is_cancel = inv.state == 'cancel'
            is_refund = inv.move_type == 'out_refund'
            factor = -1.0 if is_refund else 1.0

            total_inv = inv.amount_total * factor if not is_cancel else 0.0
            total_inv_usd = get_amount_usd(inv.amount_total, inv.currency_id, inv.invoice_date) * factor if not is_cancel else 0.0

            grand_total_facturado += total_inv
            grand_total_facturado_usd += total_inv_usd

            # Obtención de todos los pagos conciliados con esta factura
            payments_lines = []
            total_pagado_inv = 0.0
            total_pagado_inv_usd = 0.0

            if not is_cancel:
                # Extraer cobros vinculados a la factura
                matched_payments = inv._get_reconciled_payments()
                
                for pay in matched_payments:
                    pay_amount = pay.amount
                    pay_usd = get_amount_usd(pay_amount, pay.currency_id, pay.date)

                    total_pagado_inv += pay_amount
                    total_pagado_inv_usd += pay_usd

                    tipo_transaccion = 'Crédito' if pay.payment_type == 'inbound' else 'Débito'

                    payments_lines.append({
                        'journal': pay.journal_id.name,
                        'payment_ref': pay.memo or pay.payment_reference or 'N/A',
                        'tipo': tipo_transaccion,
                        'amount': pay_amount,
                        'amount_usd': pay_usd,
                        'currency': pay.currency_id,
                    })

                # Si no tiene pagos aún registrado (Venta a crédito)
                if not matched_payments:
                    payments_lines.append({
                        'journal': 'CRÉDITO / PENDIENTE',
                        'payment_ref': 'N/A',
                        'tipo': 'Pendiente',
                        'amount': inv.amount_residual * factor,
                        'amount_usd': get_amount_usd(inv.amount_residual, inv.currency_id, inv.invoice_date) * factor,
                        'currency': inv.currency_id,
                    })
                    total_pagado_inv = inv.amount_total - inv.amount_residual
                    total_pagado_inv_usd = total_inv_usd - get_amount_usd(inv.amount_residual, inv.currency_id, inv.invoice_date)

            grand_total_pagado += total_pagado_inv
            grand_total_pagado_usd += total_pagado_inv_usd

            invoice_details.append({
                'id': inv.id,
                'fecha': inv.invoice_date or inv.date,
                'name': inv.name if not is_cancel else '<<<< ANULADA >>>>',
                'partner': inv.partner_id.name if not is_cancel else '<<<< ANULADA >>>>',
                'vat': inv.partner_id.vat if not is_cancel else '',
                'move_type': 'N/C' if is_refund else ('ANU' if is_cancel else 'FAC'),
                'total_inv': total_inv,
                'total_inv_usd': total_inv_usd,
                'payments': payments_lines,
                'total_pagado_inv': total_pagado_inv,
                'total_pagado_inv_usd': total_pagado_inv_usd,
                'saldo_pendiente': inv.amount_residual if not is_cancel else 0.0,
                'saldo_pendiente_usd': get_amount_usd(inv.amount_residual, inv.currency_id, inv.invoice_date) if not is_cancel else 0.0,
                'is_cancel': is_cancel,
            })

        return {
            'doc_ids': docids,
            'doc_model': 'cuadre.diario.detalles',
            'docs': docs,
            'res_company': company,
            'currency_usd': currency_usd,
            'date_from': date_from,
            'date_to': date_to,
            'invoice_details': invoice_details,
            'grand_total_facturado': grand_total_facturado,
            'grand_total_facturado_usd': grand_total_facturado_usd,
            'grand_total_pagado': grand_total_pagado,
            'grand_total_pagado_usd': grand_total_pagado_usd,
        }