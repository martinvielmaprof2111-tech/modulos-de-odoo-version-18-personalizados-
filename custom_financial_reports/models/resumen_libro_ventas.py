from odoo import models, fields, api

class ResumenLibroVentas(models.TransientModel):
    _name = 'resumen.libro.ventas'
    _description = 'Wizard Resumen Libro de Ventas (Art. 72)'

    company_id = fields.Many2one('res.company', string='Empresa/Sucursal', default=lambda self: self.env.company, required=True)
    date_from = fields.Date(string='Desde', required=True, default=fields.Date.context_today)
    date_to = fields.Date(string='Hasta', required=True, default=fields.Date.context_today)

    def action_print_pdf(self):
        return self.env.ref('custom_financial_reports.action_report_resumen_libro_ventas').report_action(self)


class ReportResumenLibroVentas(models.AbstractModel):
    _name = 'report.custom_financial_reports.template_resumen_libro_ventas'
    _description = 'Reporte QWeb Resumen Libro de Ventas'

    def _get_report_values(self, docids, data=None):
        docs = self.env['resumen.libro.ventas'].browse(docids)
        company = docs.company_id

        # Búsqueda de facturas y notas de crédito publicadas en el rango de fechas
        invoices = self.env['account.move'].search([
            ('invoice_date', '>=', docs.date_from),
            ('invoice_date', '<=', docs.date_to),
            ('company_id', '=', company.id),
            ('move_type', 'in', ['out_invoice', 'out_refund']),
            ('state', '=', 'posted'),
        ], order='invoice_date asc')

        # Acumuladores para Facturas (Ventas Gravadas)
        fac_total = 0.0
        fac_exento = 0.0
        fac_base_16 = 0.0
        fac_iva_16 = 0.0
        fac_base_0 = 0.0
        fac_iva_0 = 0.0

        # Acumuladores para Notas de Crédito
        nc_total = 0.0
        nc_exento = 0.0
        nc_base_16 = 0.0
        nc_iva_16 = 0.0
        nc_base_0 = 0.0
        nc_iva_0 = 0.0

        for move in invoices:
            is_nc = move.move_type == 'out_refund'
            
            # Suma de total comprobante
            if is_nc:
                nc_total += move.amount_total
            else:
                fac_total += move.amount_total

            # Desglose por líneas
            for line in move.invoice_line_ids.filtered(lambda l: not l.display_type):
                subtotal = line.price_subtotal
                taxes = line.tax_ids

                if not taxes:
                    if is_nc:
                        nc_exento += subtotal
                    else:
                        fac_exento += subtotal
                else:
                    for tax in taxes:
                        if tax.amount == 16.0:
                            tax_amount = subtotal * (tax.amount / 100.0)
                            if is_nc:
                                nc_base_16 += subtotal
                                nc_iva_16 += tax_amount
                            else:
                                fac_base_16 += subtotal
                                fac_iva_16 += tax_amount
                        elif tax.amount == 0.0:
                            if tax.amount_type == 'percent' and any('exent' in (t.name or '').lower() for t in taxes):
                                if is_nc:
                                    nc_exento += subtotal
                                else:
                                    fac_exento += subtotal
                            else:
                                if is_nc:
                                    nc_base_0 += subtotal
                                else:
                                    fac_base_0 += subtotal

        # Cálculo de Totales Netos (Facturas menos Notas de Crédito)
        neto_ventas_generales = fac_total - nc_total
        neto_exento = fac_exento - nc_exento
        neto_base_16 = fac_base_16 - nc_base_16
        neto_iva_16 = fac_iva_16 - nc_iva_16
        neto_base_0 = fac_base_0 - nc_base_0
        neto_iva_0 = fac_iva_0 - nc_iva_0

        neto_base_imponible = neto_base_16 + neto_base_0
        neto_impuesto = neto_iva_16 + neto_iva_0

        retenciones_sobre_ventas = 0.0  # Ajustar con el campo o modelo de retenciones de IVA si aplica

        return {
            'doc_ids': docids,
            'doc_model': 'resumen.libro.ventas',
            'docs': docs,
            'res_company': company,
            # Facturas
            'fac_total': fac_total,
            'fac_exento': fac_exento,
            'fac_base_16': fac_base_16,
            'fac_iva_16': fac_iva_16,
            'fac_base_0': fac_base_0,
            'fac_iva_0': fac_iva_0,
            'fac_total_impuesto': fac_iva_16 + fac_iva_0,
            'fac_total_base': fac_base_16 + fac_base_0,
            # Notas de Crédito
            'nc_total': nc_total,
            'nc_exento': nc_exento,
            'nc_base_16': nc_base_16,
            'nc_iva_16': nc_iva_16,
            'nc_base_0': nc_base_0,
            'nc_iva_0': nc_iva_0,
            'nc_total_impuesto': nc_iva_16 + nc_iva_0,
            'nc_total_base': nc_base_16 + nc_base_0,
            # Totales Netos
            'neto_ventas_generales': neto_ventas_generales,
            'neto_exento': neto_exento,
            'neto_base_16': neto_base_16,
            'neto_iva_16': neto_iva_16,
            'neto_base_0': neto_base_0,
            'neto_iva_0': neto_iva_0,
            'neto_base_imponible': neto_base_imponible,
            'neto_impuesto': neto_impuesto,
            'retenciones_sobre_ventas': retenciones_sobre_ventas,
        }