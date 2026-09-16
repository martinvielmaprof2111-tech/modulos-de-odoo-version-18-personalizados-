from odoo import models, fields

# Lista global de diarios permitidos
ALLOWED_JOURNALS = [
    'FACTURAS DE VENTAS-MARACAIBO',
    'FACTURAS DE VENTAS-VALENCIA',
    'FACTURAS DE VENTAS-BARQUISIMETO'
]


class CuadreDiario(models.TransientModel):
    _name = 'cuadre.diario'
    _description = 'Wizard Cuadre Diario'

    company_id = fields.Many2one('res.company', string='Empresa/Sucursal', default=lambda self: self.env.company, required=True)
    date_from = fields.Date(string='Desde', required=True, default=fields.Date.context_today)
    date_to = fields.Date(string='Hasta', required=True, default=fields.Date.context_today)
    user_id = fields.Many2one('res.users', string='Creado Por (Usuario)')

    def action_print_pdf(self):
        return self.env.ref('custom_financial_reports.action_report_cuadre_diario').report_action(self)


class ReportCuadreDiario(models.AbstractModel):
    _name = 'report.custom_financial_reports.template_cuadre_diario'
    _description = 'Reporte QWeb Cuadre Diario'

    def _get_report_values(self, docids, data=None):
        docs = self.env['cuadre.diario'].browse(docids)
        company = docs.company_id
        date_from = docs.date_from
        date_to = docs.date_to
        user_id = docs.user_id

        currency_usd = self.env.ref('base.USD', raise_if_not_found=False) or self.env['res.currency'].sudo().search([('name', '=', 'USD')], limit=1)

        def get_amount_usd(amount, from_currency, date):
            if not currency_usd or not amount:
                return 0.0
            if from_currency == currency_usd:
                return amount
            return from_currency._convert(amount, currency_usd, company, date or fields.Date.today())

        # 1. Dominios y búsqueda de facturas
        domain_fac = [
            ('invoice_date', '>=', date_from),
            ('invoice_date', '<=', date_to),
            ('company_id', '=', company.id),
            ('journal_id.name', 'in', ALLOWED_JOURNALS),  # Usa la constante definida arriba
            ('move_type', '=', 'out_invoice'),
            ('state', '=', 'posted'),
        ]

        if user_id:
            domain_fac.append(('create_uid', '=', user_id.id))

        fac_list = self.env['account.move'].sudo().search(domain_fac, order='name asc')

        # 2. Búsqueda y filtrado de pagos
        domain_pay = [
            ('date', '>=', date_from),
            ('date', '<=', date_to),
            ('company_id', '=', company.id),
            ('payment_type', 'in', ['inbound', 'outbound']),
            ('state', 'in', ['posted', 'paid', 'in_process']),
        ]

        if user_id:
            domain_pay.append(('create_uid', '=', user_id.id))

        payments = self.env['account.payment'].sudo().search(domain_pay, order='journal_id asc, date asc, id asc')

        # Variables para vistas
        nc_list = self.env['account.move']
        canceled_invoices = self.env['account.move']
        credit_fac_list = fac_list.filtered(lambda m: m.amount_residual > 0)

        # Totales
        total_ventas = sum(fac_list.mapped('amount_total'))
        total_ventas_usd = sum(get_amount_usd(inv.amount_total, inv.currency_id, inv.invoice_date) for inv in fac_list)

        nc_emitidas = 0.0
        nc_emitidas_usd = 0.0

        ventas_credito = sum(credit_fac_list.mapped('amount_residual'))
        ventas_credito_usd = sum(get_amount_usd(inv.amount_residual, inv.currency_id, inv.invoice_date) for inv in credit_fac_list)

        total_ventas_general = total_ventas
        total_ventas_general_usd = total_ventas_usd

        # Descuentos
        total_descuentos = 0.0
        total_descuentos_usd = 0.0
        for inv in fac_list:
            for line in inv.invoice_line_ids.filtered(lambda l: l.display_type == 'product'):
                if line.discount > 0:
                    subtotal_sin_dcto = line.price_unit * line.quantity
                    desc = subtotal_sin_dcto * (line.discount / 100.0)
                    total_descuentos += desc
                    total_descuentos_usd += get_amount_usd(desc, inv.currency_id, inv.invoice_date)

        # Clasificación de pagos
        efectivo_payments = payments.filtered(lambda p: p.journal_id.type == 'cash' and p.currency_id == company.currency_id)
        divisas_payments = payments.filtered(lambda p: p.currency_id != company.currency_id)
        tarjeta_payments = payments.filtered(lambda p: any(term in p.journal_id.name.lower() for term in ['tarjeta', 'punto', 'pm', 'pago movil']) and p.id not in divisas_payments.ids)
        banco_payments = payments.filtered(lambda p: p.journal_id.type == 'bank' and p.id not in tarjeta_payments.ids and p.id not in divisas_payments.ids)

        total_efectivo = sum(efectivo_payments.mapped('amount'))
        total_efectivo_usd = sum(get_amount_usd(p.amount, p.currency_id, p.date) for p in efectivo_payments)

        total_divisas = sum(divisas_payments.mapped('amount'))
        total_divisas_usd = sum(get_amount_usd(p.amount, p.currency_id, p.date) for p in divisas_payments)

        total_tarjetas = sum(tarjeta_payments.mapped('amount'))
        total_tarjetas_usd = sum(get_amount_usd(p.amount, p.currency_id, p.date) for p in tarjeta_payments)

        total_bancos = sum(banco_payments.mapped('amount'))
        total_bancos_usd = sum(get_amount_usd(p.amount, p.currency_id, p.date) for p in banco_payments)

        ingresos_brutos = total_efectivo + total_divisas + total_tarjetas + total_bancos
        ingresos_brutos_usd = total_efectivo_usd + total_divisas_usd + total_tarjetas_usd + total_bancos_usd

        # Detalle de banco/tarjeta
        card_bank_details = []
        for p in (tarjeta_payments | banco_payments):
            ref_operacion = p.memo or p.payment_reference or (p.move_id.ref if p.move_id else '') or ''
            invoices = p.sudo().reconciled_bill_ids or p.sudo().reconciled_invoice_ids
            doc_ref = ", ".join(invoices.mapped('name')) if invoices else 'Anticipo / Abono'
            
            tipo_transaccion = 'Crédito (Ingreso)' if p.payment_type == 'inbound' else 'Débito (Egreso)'
            amount_usd = get_amount_usd(p.amount, p.currency_id, p.date)

            card_bank_details.append({
                'journal': p.journal_id.name,
                'type': tipo_transaccion,
                'ref': ref_operacion or 'N/A',
                'doc_ref': doc_ref,
                'partner': p.partner_id.name if p.partner_id else 'N/A',
                'amount': p.amount,
                'amount_usd': amount_usd,
            })

        # Vendedores
        sellers_data = {}
        for inv in fac_list:
            seller = inv.invoice_user_id or inv.user_id
            seller_id = seller.id if seller else 0
            seller_name = seller.name if seller else 'SIN VENDEDOR'

            if seller_id not in sellers_data:
                sellers_data[seller_id] = {
                    'name': seller_name,
                    'count': 0,
                    'items_qty': 0,
                    'total_amount': 0.0,
                    'total_amount_usd': 0.0,
                    'untaxed_amount': 0.0,
                    'untaxed_amount_usd': 0.0,
                }

            items_count = sum(line.quantity for line in inv.invoice_line_ids if line.display_type == 'product')
            sellers_data[seller_id]['count'] += 1
            sellers_data[seller_id]['items_qty'] += items_count
            sellers_data[seller_id]['total_amount'] += inv.amount_total
            sellers_data[seller_id]['total_amount_usd'] += get_amount_usd(inv.amount_total, inv.currency_id, inv.invoice_date)
            sellers_data[seller_id]['untaxed_amount'] += inv.amount_untaxed
            sellers_data[seller_id]['untaxed_amount_usd'] += get_amount_usd(inv.amount_untaxed, inv.currency_id, inv.invoice_date)

        sellers_list = sorted(sellers_data.values(), key=lambda x: x['total_amount'], reverse=True)
        
        total_seller_vtas = sum(s['count'] for s in sellers_list)
        total_seller_arts = sum(s['items_qty'] for s in sellers_list)
        total_seller_untaxed = sum(s['untaxed_amount'] for s in sellers_list)
        total_seller_untaxed_usd = sum(s['untaxed_amount_usd'] for s in sellers_list)
        total_seller_amount = sum(s['total_amount'] for s in sellers_list)
        total_seller_amount_usd = sum(s['total_amount_usd'] for s in sellers_list)

        return {
            'doc_ids': docids,
            'doc_model': 'cuadre.diario',
            'docs': docs,
            'res_company': company,
            'currency_usd': currency_usd,
            'date_from': date_from,
            'date_to': date_to,
            'payments': payments,
            'total_ventas': total_ventas,
            'total_ventas_usd': total_ventas_usd,
            'count_ventas': len(fac_list),
            'nc_emitidas': nc_emitidas,
            'nc_emitidas_usd': nc_emitidas_usd,
            'count_nc': len(nc_list),
            'ventas_credito': ventas_credito,
            'ventas_credito_usd': ventas_credito_usd,
            'count_credito': len(credit_fac_list),
            'total_ventas_general': total_ventas_general,
            'total_ventas_general_usd': total_ventas_general_usd,
            'count_anulados': len(canceled_invoices),
            'total_descuentos': total_descuentos,
            'total_descuentos_usd': total_descuentos_usd,
            'total_efectivo': total_efectivo,
            'total_efectivo_usd': total_efectivo_usd,
            'count_efectivo': len(efectivo_payments),
            'total_divisas': total_divisas,
            'total_divisas_usd': total_divisas_usd,
            'count_divisas': len(divisas_payments),
            'total_tarjetas': total_tarjetas,
            'total_tarjetas_usd': total_tarjetas_usd,
            'count_tarjetas': len(tarjeta_payments),
            'total_bancos': total_bancos,
            'total_bancos_usd': total_bancos_usd,
            'count_bancos': len(banco_payments),
            'ingresos_brutos': ingresos_brutos,
            'ingresos_brutos_usd': ingresos_brutos_usd,
            'card_bank_details': card_bank_details,
            'fac_desde': fac_list[0].name if fac_list else 'N/A',
            'fac_hasta': fac_list[-1].name if fac_list else 'N/A',
            'nc_desde': nc_list[0].name if nc_list else 'N/A',
            'nc_hasta': nc_list[-1].name if nc_list else 'N/A',
            'sellers_list': sellers_list,
            'total_seller_vtas': total_seller_vtas,
            'total_seller_arts': total_seller_arts,
            'total_seller_untaxed': total_seller_untaxed,
            'total_seller_untaxed_usd': total_seller_untaxed_usd,
            'total_seller_amount': total_seller_amount,
            'total_seller_amount_usd': total_seller_amount_usd,
        }