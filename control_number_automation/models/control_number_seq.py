# -*- coding: utf-8 -*-
import re
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError

class InvoiceControlSequence(models.Model):
    _name = 'invoice.control.sequence'
    _description = 'Secuencia de Número de Control Fiscal'

    name = fields.Char(string='Nombre de la Secuencia', required=True)
    company_id = fields.Many2one(
        'res.company', string='Compañía', required=True, 
        default=lambda self: self.env.company
    )
    journal_type = fields.Selection([
        ('sale', 'Ventas (Clientes)'),
        ('purchase', 'Compras (Proveedores)'),
        ('general', 'Inventario / Misceláneos (General)')
    ], string='Dirección del Diario', required=True)

    prefix = fields.Char(string='Prefijo', help='Ejemplo: 00-')
    suffix = fields.Char(string='Sufijo', help='Ejemplo: /A')
    padding = fields.Integer(string='Tamaño del Número (Padding)', default=8, required=True)

    start_number = fields.Integer(string='Número Inicial', default=1, required=True)
    end_number = fields.Integer(string='Número Final', default=99999999, required=True)
    next_number = fields.Integer(string='Siguiente Número', default=1, required=True)

    active = fields.Boolean(string='Activa', default=False)

    @api.constrains('active', 'company_id', 'journal_type')
    def _check_single_active_sequence(self):
        for rec in self:
            if rec.active:
                domain = [
                    ('company_id', '=', rec.company_id.id),
                    ('journal_type', '=', rec.journal_type),
                    ('active', '=', True),
                    ('id', '!=', rec.id)
                ]
                if self.search_count(domain) > 0:
                    raise ValidationError(_(
                        "Ya existe una secuencia activa para la combinación de Compañía y Dirección del Diario."
                    ))

    @api.onchange('journal_type', 'company_id')
    def _onchange_journal_type_suggest_number(self):
        """ Sugiere el siguiente número de control al cambiar diario o compañía """
        if self.company_id and self.journal_type:
            self.recalculate_next_number()

    def action_activate_sequence(self):
        self.ensure_one()
        other_active = self.search([
            ('company_id', '=', self.company_id.id),
            ('journal_type', '=', self.journal_type),
            ('active', '=', True),
            ('id', '!=', self.id)
        ])
        if other_active:
            other_active.write({'active': False})
        
        self.recalculate_next_number()
        self.write({'active': True})

    def action_deactivate_sequence(self):
        self.ensure_one()
        self.write({'active': False})

    def recalculate_next_number(self):
        """ Busca el número histórico en las facturas publicadas """
        self.ensure_one()
        if self.journal_type == 'sale':
            move_types = ['out_invoice', 'out_refund']
        elif self.journal_type == 'purchase':
            move_types = ['in_invoice', 'in_refund']
        else:
            move_types = ['entry']

        last_move = self.env['account.move'].search([
            ('company_id', '=', self.company_id.id),
            ('move_type', 'in', move_types),
            ('state', '=', 'posted')
        ], order='id desc', limit=1)

        if last_move:
            if last_move.nro_ctrl:
                nums = re.findall(r'\d+', last_move.nro_ctrl)
                if nums:
                    self.next_number = int(nums[-1]) + 1
                    return
            if last_move.name and last_move.name != '/':
                nums = re.findall(r'\d+', last_move.name)
                if nums:
                    self.next_number = int(nums[-1]) + 1
                    return

        self.next_number = self.start_number or 1

    def get_next_control_number_formatted(self):
        self.ensure_one()
        num_str = str(self.next_number).zfill(self.padding)
        prefix = self.prefix or ''
        suffix = self.suffix or ''
        return f"{prefix}{num_str}{suffix}"