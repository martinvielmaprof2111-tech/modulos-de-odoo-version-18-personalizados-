# -*- coding: utf-8 -*-
import re
from odoo import api, SUPERUSER_ID

def post_init_hook(env_or_cr, registry=None):
    """
    Inicializa las configuraciones de Secuencias de Control creando 
    un registro individual por cada diario de ventas de cada sucursal.
    """
    if isinstance(env_or_cr, api.Environment):
        env = env_or_cr
    else:
        env = api.Environment(env_or_cr, SUPERUSER_ID, {})

    companies = env['res.company'].search([])
    
    for company in companies:
        sale_journals = env['account.journal'].search([
            ('company_id', '=', company.id),
            ('type', '=', 'sale')
        ])

        for journal in sale_journals:
            # Verificar si este diario específico ya tiene una secuencia asignada
            existing_seq = env['invoice.control.sequence'].search([
                ('company_id', '=', company.id),
                ('journal_ids', 'in', [journal.id]),
                ('active', '=', True)
            ], limit=1)

            if not existing_seq:
                # Calcular el mayor número de control usado en facturas vinculadas a este diario
                moves = env['account.move'].search([
                    ('company_id', '=', company.id),
                    ('journal_id', '=', journal.id),
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

                next_num = max_num + 1 if max_num > 0 else 1

                # Crear un registro individual por cada diario
                env['invoice.control.sequence'].create({
                    'name': f'Secuencia Nro. Control - {journal.name} ({company.name})',
                    'company_id': company.id,
                    'journal_ids': [(6, 0, [journal.id])],
                    'prefix': '00-',
                    'padding': 8,
                    'start_number': 1,
                    'next_number': next_num,
                    'active': True,
                })