from odoo import models, fields, api

class LibroVentasDiario(models.TransientModel):
    _name = 'libro.ventas.diario'
    _description = 'Wizard Libro de Ventas Diario (Art. 77)'

    company_id = fields.Many2one('res.company', string='Empresa/Sucursal', default=lambda self: self.env.company, required=True)
    date_from = fields.Date(string='Desde', required=True, default=fields.Date.context_today)
    date_to = fields.Date(string='Hasta', required=True, default=fields.Date.context_today)
    
    date = fields.Date(string='Fecha', compute='_compute_date')

    @api.depends('date_from')
    def _compute_date(self):
        for rec in self:
            rec.date = rec.date_from

    def action_print_pdf(self):
        return self.env.ref('custom_financial_reports.action_report_libro_ventas_diario').report_action(self)


class ReportLibroVentasDiario(models.AbstractModel):
    _name = 'report.custom_financial_reports.template_libro_ventas_diario'
    _description = 'Reporte QWeb Libro de Ventas Diario'

    def _get_report_values(self, docids, data=None):
        docs = self.env['libro.ventas.diario'].browse(docids)
        company = docs.company_id
        date_from = docs.date_from
        date_to = docs.date_to

        # Moneda USD para la conversión y formato en QWeb
        currency_usd = self.env.ref('base.USD', raise_if_not_found=False) or self.env['res.currency'].search([('name', '=', 'USD')], limit=1)

        # Búsqueda de facturas y notas de crédito
        invoices = self.env['account.move'].search([
            ('company_id', '=', company.id),
            ('move_type', 'in', ['out_invoice', 'out_refund']),
            ('state', 'in', ['posted', 'cancel']),
            '|',
                '&', ('invoice_date', '>=', date_from), ('invoice_date', '<=', date_to),
                '&', ('date', '>=', date_from), ('date', '<=', date_to),
        ], order='invoice_date asc, name asc')

        invoice_list = []
        tot_ventas_con_imp = 0.0
        tot_monto_usd = 0.0

        for inv in invoices:
            is_cancel = inv.state == 'cancel'
            is_refund = inv.move_type == 'out_refund'
            factor = -1.0 if is_refund else 1.0

            if is_cancel:
                total_con_imp = 0.0
                monto_usd = 0.0
            else:
                total_con_imp = inv.amount_total * factor
                
                # Conversión a Dólares
                if inv.currency_id == currency_usd:
                    monto_usd = total_con_imp
                elif currency_usd:
                    monto_usd = inv.currency_id._convert(
                        inv.amount_total,
                        currency_usd,
                        company,
                        inv.invoice_date or inv.date or fields.Date.today()
                    ) * factor
                else:
                    monto_usd = 0.0

            tot_ventas_con_imp += total_con_imp
            tot_monto_usd += monto_usd

            num_control = getattr(inv, 'l10n_ve_control_number', '') or inv.ref or inv.name
            factura_afectada = inv.reversed_entry_id.name if inv.reversed_entry_id else ''

            invoice_list.append({
                'fecha': inv.invoice_date or inv.date,
                'tipo_doc': 'N/C' if is_refund else ('ANU' if is_cancel else 'FAC'),
                'num_fac': inv.name if not is_cancel else '<<<< ANULADA >>>>',
                'num_control': num_control,
                'fac_afectada': factura_afectada,
                'partner_name': inv.partner_id.name if not is_cancel else '<<<< ANULADA >>>>',
                'partner_vat': inv.partner_id.vat if not is_cancel else '',
                'total_con_imp': total_con_imp,
                'monto_usd': monto_usd,
                'is_cancel': is_cancel,
                'currency': inv.currency_id,
            })

        return {
            'doc_ids': docids,
            'doc_model': 'libro.ventas.diario',
            'docs': docs,
            'res_company': company,
            'currency_usd': currency_usd,
            'date_from': date_from,
            'date_to': date_to,
            'invoice_list': invoice_list,
            'tot_ventas_con_imp': tot_ventas_con_imp,
            'tot_monto_usd': tot_monto_usd,
        }