# -*- coding: utf-8 -*-
from odoo import models, fields, api

class AccountMoveReversal(models.TransientModel):
    _inherit = 'account.move.reversal'

    nro_ctrl = fields.Char(
        string='Número de Control',
        help='Número de control fiscal para la nota de crédito.'
    )

    def _prepare_default_reversal_values(self, move):
        res = super(AccountMoveReversal, self)._prepare_default_reversal_values(move)
        if self.nro_ctrl:
            res['nro_ctrl'] = self.nro_ctrl
        return res