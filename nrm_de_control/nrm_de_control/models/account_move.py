# -*- coding: utf-8 -*-
import re
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError

class AccountMove(models.Model):
    _inherit = 'account.move'

    nro_ctrl = fields.Char(
        string='Número de Control',
        copy=False,
        index=True,
        tracking=True
    )

    nro_ctrl_preview = fields.Char(
        string='Siguiente Nro. Control Configurado',
        compute='_compute_nro_ctrl_preview',
        help='Muestra el próximo correlativo que asignará la secuencia o la sucursal'
    )

    @api.depends('journal_id', 'company_id', 'move_type')
    def _compute_nro_ctrl_preview(self):
        for move in self:
            if move.move_type in ['out_invoice', 'out_refund', 'out_receipt'] and not move.nro_ctrl:
                sequence = self.env['invoice.control.sequence'].search([
                    ('company_id', '=', move.company_id.id),
                    ('journal_ids', 'in', [move.journal_id.id]),
                    ('active', '=', True)
                ], limit=1)

                if sequence:
                    move.nro_ctrl_preview = sequence.get_next_number_formatted()
                else:
                    moves = self.search([
                        ('company_id', '=', move.company_id.id),
                        ('move_type', 'in', ['out_invoice', 'out_refund', 'out_receipt']),
                        ('nro_ctrl', '!=', False),
                        ('nro_ctrl', '!=', '')
                    ])

                    max_num = 0
                    for m in moves:
                        nums = re.findall(r'\d+', m.nro_ctrl)
                        if nums:
                            val = int(nums[-1])
                            if val > max_num:
                                max_num = val

                    next_val = max_num + 1 if max_num > 0 else 1
                    move.nro_ctrl_preview = f"00-{str(next_val).zfill(8)}"
            else:
                move.nro_ctrl_preview = False

    def action_post(self):
        for move in self:
            if move.move_type in ['out_invoice', 'out_refund', 'out_receipt'] and not getattr(move, 'maq_fiscal_p', False):
                if not move.nro_ctrl:
                    sequence = self.env['invoice.control.sequence'].search([
                        ('company_id', '=', move.company_id.id),
                        ('journal_ids', 'in', [move.journal_id.id]),
                        ('active', '=', True)
                    ], limit=1)

                    if sequence:
                        move.nro_ctrl = sequence.get_next_number_and_increment()
                    else:
                        moves = self.search([
                            ('company_id', '=', move.company_id.id),
                            ('move_type', 'in', ['out_invoice', 'out_refund', 'out_receipt']),
                            ('nro_ctrl', '!=', False),
                            ('nro_ctrl', '!=', ''),
                            ('id', '!=', move.id)
                        ])

                        max_num = 0
                        for m in moves:
                            nums = re.findall(r'\d+', m.nro_ctrl)
                            if nums:
                                val = int(nums[-1])
                                if val > max_num:
                                    max_num = val

                        next_val = max_num + 1 if max_num > 0 else 1
                        move.nro_ctrl = f"00-{str(next_val).zfill(8)}"

            elif move.move_type in ['in_invoice', 'in_refund', 'in_receipt']:
                if not move.nro_ctrl:
                    raise ValidationError(_(
                        "Debe ingresar el Número de Control del proveedor antes de publicar la factura."
                    ))

        return super(AccountMove, self).action_post()