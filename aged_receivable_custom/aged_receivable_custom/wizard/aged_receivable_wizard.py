# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import UserError
import datetime

class AgedReceivableWizard(models.TransientModel):
    _name = 'aged.receivable.wizard'
    _description = 'Wizard Resumen de Vencimiento CxC'

    date_at = fields.Date(
        string='Fecha de Corte', 
        default=fields.Date.context_today, 
        required=True
    )
    currency_id = fields.Many2one(
        'res.currency', 
        string='Moneda', 
        required=True, 
        default=lambda self: self.env.company.currency_id
    )
    user_ids = fields.Many2many(
        'res.users', 
        string='Vendedores'
    )
    state_ids = fields.Many2many(
        'res.country.state', 
        string='Estados', 
        domain="[('country_id.code', '=', 'VE')]"
    )
    category_ids = fields.Many2many(
        'res.partner.category', 
        string='Categorías / Grupos'
    )

    def print_report(self):
        self.ensure_one()
        
        # Dominio base para facturas y notas de crédito de clientes
        domain = [
            ('move_type', 'in', ['out_invoice', 'out_refund']),
            ('state', '=', 'posted'),
            ('payment_state', 'not in', ['paid', 'reversed']),
            ('invoice_date', '<=', self.date_at),
            ('company_id', '=', self.env.company.id),
        ]

        if self.user_ids:
            domain.append(('invoice_user_id', 'in', self.user_ids.ids))

        # Filtros opcionales aplicables al modelo res.partner
        partner_domain = []
        if self.state_ids:
            partner_domain.append(('state_id', 'in', self.state_ids.ids))
        if self.category_ids:
            partner_domain.append(('category_id', 'in', self.category_ids.ids))

        if partner_domain:
            partners = self.env['res.partner'].search(partner_domain)
            domain.append(('partner_id', 'in', partners.ids))

        moves = self.env['account.move'].search(domain)

        if not moves:
            raise UserError(_("No se encontraron registros con los filtros seleccionados."))

        # Estructura de Agrupación: ESTADO -> CLIENTE
        raw_data = {}
        totales_general = {'b1': 0.0, 'b2': 0.0, 'b3': 0.0, 'b4': 0.0, 'b5': 0.0, 'total': 0.0}

        for move in moves:
            estado_name = move.partner_id.state_id.name or 'SIN ESTADO ASIGNADO'
            cliente_name = move.partner_id.name or 'SIN CLIENTE'

            # Conversión de moneda al tipo seleccionado
            monto = move.amount_residual
            if move.currency_id != self.currency_id:
                monto = move.currency_id._convert(
                    monto,
                    self.currency_id,
                    self.env.company,
                    move.invoice_date or fields.Date.today()
                )

            # Clasificación por tramos de vencimiento
            dias = (self.date_at - move.invoice_date_due).days if move.invoice_date_due else 0

            b1 = b2 = b3 = b4 = b5 = 0.0
            if dias <= 15:
                b1 = monto
            elif 16 <= dias <= 30:
                b2 = monto
            elif 31 <= dias <= 60:
                b3 = monto
            elif 61 <= dias <= 90:
                b4 = monto
            else:
                b5 = monto

            if estado_name not in raw_data:
                raw_data[estado_name] = {}

            if cliente_name not in raw_data[estado_name]:
                raw_data[estado_name][cliente_name] = {
                    'b1': 0.0, 'b2': 0.0, 'b3': 0.0, 'b4': 0.0, 'b5': 0.0, 'total': 0.0
                }

            raw_data[estado_name][cliente_name]['b1'] += b1
            raw_data[estado_name][cliente_name]['b2'] += b2
            raw_data[estado_name][cliente_name]['b3'] += b3
            raw_data[estado_name][cliente_name]['b4'] += b4
            raw_data[estado_name][cliente_name]['b5'] += b5
            raw_data[estado_name][cliente_name]['total'] += monto

            totales_general['b1'] += b1
            totales_general['b2'] += b2
            totales_general['b3'] += b3
            totales_general['b4'] += b4
            totales_general['b5'] += b5
            totales_general['total'] += monto

        # Ordenamiento alfabético por Estado y por Cliente
        report_data = {}
        for estado in sorted(raw_data.keys()):
            report_data[estado] = {}
            for cliente in sorted(raw_data[estado].keys()):
                report_data[estado][cliente] = raw_data[estado][cliente]

        # Formateo de etiquetas para el encabezado del reporte QWeb
        data = {
            'date_at': self.date_at.strftime('%d/%m/%Y'),
            'currency_name': self.currency_id.name,
            'user_name': ", ".join(self.user_ids.mapped('name')) if self.user_ids else 'TODOS LOS VENDEDORES',
            'state_name': ", ".join(self.state_ids.mapped('name')) if self.state_ids else 'TODOS LOS ESTADOS',
            'category_name': ", ".join(self.category_ids.mapped('name')) if self.category_ids else 'TODOS LOS GRUPOS',
        }

        return self.env.ref('aged_receivable_custom.action_report_aged_receivable_custom').report_action(
            self, data={
                'data': data,
                'report_data': report_data,
                'totales_general': totales_general,
                'print_date': datetime.datetime.now().strftime('%d/%m/%Y %H:%M:%S'),
            }
        )