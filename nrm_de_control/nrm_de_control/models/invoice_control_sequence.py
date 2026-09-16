# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError

class InvoiceControlSequence(models.Model):
    _name = 'invoice.control.sequence'
    _description = 'Secuencia de Número de Control Fiscal por Sucursal y Diario'
    _order = 'id desc'

    name = fields.Char(string='Nombre de Secuencia', required=True)
    company_id = fields.Many2one(
        'res.company', string='Compañía / Sucursal', required=True,
        default=lambda self: self.env.company
    )
    
    journal_ids = fields.Many2many(
        'account.journal',
        'rel_control_sequence_journal',
        'sequence_id',
        'journal_id',
        string='Diarios Permitidos',
        domain="[('company_id', '=', company_id), ('type', 'in', ('sale', 'purchase'))]",
        help='Selecciona los diarios contables vinculados a esta secuencia.'
    )

    prefix = fields.Char(string='Prefijo', help='Ejemplo: 00-')
    suffix = fields.Char(string='Sufijo', help='Ejemplo: /A')
    padding = fields.Integer(string='Tamaño (Padding)', default=8, required=True)

    start_number = fields.Integer(string='Número Inicial', default=1, required=True)
    end_number = fields.Integer(string='Número Final', default=99999999, required=True)
    next_number = fields.Integer(string='Siguiente Número', default=1, required=True)
    
    active = fields.Boolean(string='Activa', default=True)

    _sql_constraints = [
        ('check_padding', 'CHECK(padding > 0)', 'El padding debe ser mayor a 0.'),
        ('check_next_number', 'CHECK(next_number > 0)', 'El siguiente número debe ser mayor a 0.')
    ]

    @api.constrains('active', 'company_id', 'journal_ids')
    def _check_unique_sequence_per_journal(self):
        for rec in self:
            if rec.active and rec.journal_ids:
                overlapping = self.search([
                    ('company_id', '=', rec.company_id.id),
                    ('active', '=', True),
                    ('id', '!=', rec.id),
                    ('journal_ids', 'in', rec.journal_ids.ids)
                ])
                if overlapping:
                    journals_names = ", ".join(overlapping.mapped('journal_ids.name'))
                    raise ValidationError(_(
                        "Los siguientes diarios ya poseen una secuencia activa en la sucursal '%s': %s"
                    ) % (rec.company_id.name, journals_names))

    def get_next_number_formatted(self):
        """Retorna el número formateado actual sin incrementarlo."""
        self.ensure_one()
        return f"{self.prefix or ''}{str(self.next_number).zfill(self.padding)}{self.suffix or ''}"

    def get_next_number_and_increment(self):
        self.ensure_one()
        if self.end_number and self.next_number > self.end_number:
            raise ValidationError(_(
                "La secuencia '%s' ha alcanzado su límite máximo (%s)."
            ) % (self.name, self.end_number))
            
        formatted_num = self.get_next_number_formatted()
        self.sudo().write({'next_number': self.next_number + 1})
        return formatted_num