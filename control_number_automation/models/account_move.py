# -*- coding: utf-8 -*-
import re
from odoo import models, fields, api, _

class AccountMove(models.Model):
    _inherit = 'account.move'

    nro_ctrl = fields.Char(
        string='Número de Control',
        copy=False,
        index=True,
        tracking=True,
        help='Número de Control Fiscal asignado a la factura.'
    )

    def _get_journal_direction(self):
        self.ensure_one()
        if self.move_type in ['out_invoice', 'out_refund']:
            return 'sale'
        elif self.move_type in ['in_invoice', 'in_refund']:
            return 'purchase'
        return 'general'

    @api.onchange('name', 'journal_id', 'company_id')
    def _onchange_set_control_number(self):
        if self.state == 'draft' and not self.nro_ctrl and self.company_id:
            direction = self._get_journal_direction()
            sequence = self.env['invoice.control.sequence'].search([
                ('company_id', '=', self.company_id.id),
                ('journal_type', '=', direction),
                ('active', '=', True)
            ], limit=1)

            if sequence:
                if sequence.end_number and sequence.next_number > sequence.end_number:
                    return {
                        'warning': {
                            'title': _("Secuencia Agotada"),
                            'message': _("La secuencia activa '%s' llegó a su límite (%s).") % (sequence.name, sequence.end_number)
                        }
                    }
                self.nro_ctrl = sequence.get_next_control_number_formatted()

    @api.onchange('nro_ctrl')
    def _onchange_check_control_number_integrity(self):
        if not self.nro_ctrl or self.state != 'draft':
            return

        # 1. Alerta por Duplicados
        duplicate = self.env['account.move'].search([
            ('id', '!=', self._origin.id if self._origin else self.id),
            ('company_id', '=', self.company_id.id),
            ('nro_ctrl', '=', self.nro_ctrl)
        ], limit=1)

        if duplicate:
            return {
                'warning': {
                    'title': _("⚠️ ¡Advertencia: Número Duplicado!"),
                    'message': _(
                        "El número de control '%s' ya ha sido asignado a la factura %s."
                    ) % (self.nro_ctrl, duplicate.name or 'en borrador')
                }
            }

        # 2. Alerta por Salto de Correlativo (Anticipación)
        last_move = self.env['account.move'].search([
            ('journal_id', '=', self.journal_id.id),
            ('state', '=', 'posted')
        ], order='id desc', limit=1)

        if last_move and last_move.name and last_move.name != '/':
            invoice_nums = re.findall(r'\d+', last_move.name)
            control_nums = re.findall(r'\d+', self.nro_ctrl)

            if invoice_nums and control_nums:
                last_invoice_int = int(invoice_nums[-1])
                current_control_int = int(control_nums[-1])
                expected_next = last_invoice_int + 1

                if current_control_int > expected_next:
                    return {
                        'warning': {
                            'title': _("ℹ️ ¡Notificación: Salto de Correlativo!"),
                            'message': _(
                                "Se está anticipando en la numeración. El último número publicado "
                                "es '%s' (siguiente esperado: %s) y usted colocó '%s'."
                            ) % (last_move.name, expected_next, self.nro_ctrl)
                        }
                    }

    def action_post(self):
        res = super(AccountMove, self).action_post()
        for move in self:
            if move.nro_ctrl:
                direction = move._get_journal_direction()
                sequence = self.env['invoice.control.sequence'].search([
                    ('company_id', '=', move.company_id.id),
                    ('journal_type', '=', direction),
                    ('active', '=', True)
                ], limit=1)

                if sequence:
                    nums = re.findall(r'\d+', move.nro_ctrl)
                    if nums:
                        actual_num_used = int(nums[-1])
                        if actual_num_used >= sequence.next_number:
                            sequence.sudo().write({'next_number': actual_num_used + 1})
        return res