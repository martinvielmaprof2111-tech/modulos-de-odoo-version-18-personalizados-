from odoo import models, fields

class RelacionCobranza(models.TransientModel):
    _name = 'relacion.cobranza'
    _description = 'Wizard Relación de Cobranza'

    company_id = fields.Many2one('res.company', string='Empresa/Sucursal', default=lambda self: self.env.company, required=True)
    date_from = fields.Date(string='Desde', required=True, default=fields.Date.context_today)
    date_to = fields.Date(string='Hasta', required=True, default=fields.Date.context_today)
    user_id = fields.Many2one('res.users', string='Creado Por (Usuario)')

    def action_print_pdf(self):
        return self.env.ref('custom_financial_reports.action_report_relacion_cobranza').report_action(self)


class ReportRelacionCobranza(models.AbstractModel):
    _name = 'report.custom_financial_reports.template_relacion_cobranza'
    _description = 'Reporte QWeb Relación de Cobranza'

    def _get_report_values(self, docids, data=None):
        docs = self.env['relacion.cobranza'].browse(docids)
        company = docs.company_id

        domain_payments = [
            ('date', '>=', docs.date_from),
            ('date', '<=', docs.date_to),
            ('company_id', '=', company.id),
            ('payment_type', '=', 'inbound'),
            ('state', '=', 'posted'),
        ]

        payments = self.env['account.payment'].sudo().search(domain_payments, order='date asc, id asc')

        payment_lines = []
        processed_payment_ids = set()
        total_bs = 0.0
        total_divisas = 0.0

        currency_usd = self.env.ref('base.USD', raise_if_not_found=False) or self.env['res.currency'].sudo().search([('name', '=', 'USD')], limit=1)

        def get_rate_from_move_or_date(move, date):
            """Obtiene la tasa BCV/USD según la factura o la fecha de la transacción"""
            if not currency_usd:
                return 1.0
            # Si la factura/asiento tiene una tasa guardada en campos personalizados
            if move and hasattr(move, 'tax_today') and move.tax_today:
                return move.tax_today
            if move and hasattr(move, 'custom_rate') and move.custom_rate:
                return move.custom_rate
            
            # De lo contrario, tasa oficial del día de la factura o pago
            rate_date = move.invoice_date or move.date if move else date
            converted = currency_usd._convert(1.0, company.currency_id, company, rate_date or fields.Date.today())
            return converted if converted > 0 else 1.0

        # 1. EVALUACIÓN DE PAGOS REGISTRADOS
        for pay in payments:
            invoices = pay.sudo().reconciled_bill_ids or pay.sudo().reconciled_invoice_ids
            
            # Filtro opcional por Usuario Creador (Pago o Facturas cobradas)
            if docs.user_id:
                inv_creators = invoices.mapped('create_uid.id') if invoices else []
                if pay.create_uid.id != docs.user_id.id and docs.user_id.id not in inv_creators:
                    continue

            processed_payment_ids.add(pay.id)
            
            ref_operacion = pay.memo or pay.payment_reference or (pay.move_id.ref if pay.move_id else '') or ''
            invoice_ref = ", ".join(invoices.mapped('name')) if invoices else (ref_operacion or 'Abono / Anticipo')
            creado_por = ", ".join(set(invoices.mapped('create_uid.name'))) if invoices else pay.create_uid.name
            plazo_pago = ", ".join(set(invoices.mapped('invoice_payment_term_id.name'))) if invoices and invoices.mapped('invoice_payment_term_id') else 'Pago Inmediato'
            
            primary_inv = invoices[0] if invoices else None

            # DETERMINAR MONTO BS, TASA Y DIVISA
            if pay.currency_id == currency_usd:
                # Caso A: El pago se registró en USD (ej. Zelle / Binance)
                monto_divisa = pay.amount
                
                # Buscamos la tasa desde la factura cobrada o del pago
                tasa = get_rate_from_move_or_date(primary_inv or pay.move_id, pay.date)
                
                # Monto en Bolívares según la tasa del documento o contabilidad
                line_bs = pay.move_id.line_ids.filtered(lambda l: l.account_id.account_type in ('asset_receivable', 'asset_cash') and (l.debit > 0 or l.credit > 0))
                monto_bs = sum(line_bs.mapped(lambda l: abs(l.debit - l.credit))) if line_bs else (monto_divisa * tasa)
                
                if monto_bs > 0 and monto_divisa > 0:
                    tasa = monto_bs / monto_divisa

            else:
                # Caso B: El pago se registró en Bs
                monto_bs = pay.amount
                
                # Obtenemos la tasa de la factura cobrada (si la factura era en USD) o del día
                tasa = get_rate_from_move_or_date(primary_inv or pay.move_id, pay.date)
                
                # Si la factura estaba expresada en USD o la compañía maneja USD
                if primary_inv and primary_inv.currency_id == currency_usd:
                    monto_divisa = monto_bs / tasa if tasa else 0.0
                else:
                    monto_divisa = monto_bs / tasa if tasa else 0.0

            total_bs += monto_bs
            total_divisas += monto_divisa

            payment_lines.append({
                'payment': pay,
                'doc_num': pay.name,
                'fecha': pay.date,
                'creado_por': creado_por,
                'plazo_pago': plazo_pago,
                'cliente': pay.partner_id.name if pay.partner_id else 'N/A',
                'forma_pago': pay.journal_id.name if pay.journal_id else 'N/A',
                'ref_doc': invoice_ref,
                'num_operacion': ref_operacion or 'N/A',
                'monto_bs': monto_bs,
                'tasa': tasa,
                'monto_divisa': monto_divisa,
            })

        # 2. EVALUACIÓN DE CONCILIACIONES PARCIALES (NOTAS DE CRÉDITO O CRUCES DIRECTOS DE FACTURAS)
        reconciles = self.env['account.partial.reconcile'].sudo().search([
            ('max_date', '>=', docs.date_from),
            ('max_date', '<=', docs.date_to),
            ('company_id', '=', company.id),
        ])

        for rec in reconciles:
            credit_line = rec.credit_move_id
            debit_line = rec.debit_move_id

            if credit_line.account_id.account_type == 'asset_receivable':
                pay_line, inv_line = credit_line, debit_line
            elif debit_line.account_id.account_type == 'asset_receivable':
                pay_line, inv_line = debit_line, credit_line
            else:
                continue

            if pay_line.payment_id and pay_line.payment_id.id in processed_payment_ids:
                continue

            inv_move = inv_line.move_id

            if docs.user_id:
                if inv_move.create_uid.id != docs.user_id.id and pay_line.move_id.create_uid.id != docs.user_id.id:
                    continue

            monto_bs = rec.amount
            tasa = get_rate_from_move_or_date(inv_move, rec.max_date)
            monto_divisa = monto_bs / tasa if tasa else 0.0

            total_bs += monto_bs
            total_divisas += monto_divisa

            creado_por = inv_move.create_uid.name if inv_move else 'N/A'
            plazo_pago = inv_move.invoice_payment_term_id.name if inv_move and inv_move.invoice_payment_term_id else 'Pago Inmediato'

            payment_lines.append({
                'payment': pay_line.move_id,
                'doc_num': pay_line.move_id.name,
                'fecha': rec.max_date,
                'creado_por': creado_por,
                'plazo_pago': plazo_pago,
                'cliente': pay_line.partner_id.name if pay_line.partner_id else 'N/A',
                'forma_pago': pay_line.journal_id.name if pay_line.journal_id else 'N/A',
                'ref_doc': inv_move.name or 'Conciliación Directa',
                'num_operacion': pay_line.move_id.ref or 'N/A',
                'monto_bs': monto_bs,
                'tasa': tasa,
                'monto_divisa': monto_divisa,
            })

        return {
            'doc_ids': docids,
            'doc_model': 'relacion.cobranza',
            'docs': docs,
            'res_company': company,
            'payment_lines': payment_lines,
            'total_bs': total_bs,
            'total_divisas': total_divisas,
            'total_cambio': total_divisas,
        }