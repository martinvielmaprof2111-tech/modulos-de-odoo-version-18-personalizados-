# -*- coding: utf-8 -*-

import re
import logging
from odoo import models, fields, api
from odoo.exceptions import ValidationError
from odoo.addons.odoo_icompras_integration.utils.icompras_utils_exportador import IcomprasDataExporter

_logger = logging.getLogger(__name__)

class IcomprasConfig(models.Model):
    _name = 'icompras.config'
    _description = 'Configuración de Integración iCompras360'
    _rec_name = 'cod_isb'

    cod_isb = fields.Char(
        string='Código ISB (RIF de la Farmacia)', 
        required=True,
        help='RIF de la farmacia sin guiones y solo números (Ej. 404024212).'
    )
    
    api_token = fields.Char(
        string='Token de Seguridad API', 
        required=True,
        help='Token secreto que validará las peticiones externas al endpoint.'
    )

    active = fields.Boolean(
        string='Activo', 
        default=True
    )

    company_id = fields.Many2one(
        'res.company', 
        string='Compañía/Farmacia', 
        default=lambda self: self.env.company,
        required=True
    )

    @api.model_create_multi
    def create(self, vals_list):
        """Asegura la limpieza del RIF al crear el registro."""
        for vals in vals_list:
            if 'cod_isb' in vals and vals['cod_isb']:
                vals['cod_isb'] = re.sub(r'[^0-9]', '', vals['cod_isb'])
        return super(IcomprasConfig, self).create(vals_list)

    def write(self, vals):
        """Asegura la limpieza del RIF al actualizar el registro."""
        if 'cod_isb' in vals and vals['cod_isb']:
            vals['cod_isb'] = re.sub(r'[^0-9]', '', vals['cod_isb'])
        return super(IcomprasConfig, self).write(vals)

    def action_test_configuration(self):
        """
        Método de prueba para la Fase 2.
        Invoca al motor de utilidades y procesa una muestra pequeña del inventario 
        coincidiendo exactamente con el filtro estricto del endpoint.
        """
        self.ensure_one()
        _logger.info("======================================================")
        _logger.info("[iCompras360 LOG] Iniciando simulación de traza (Fase 2)...")
        
        # Alineamos la búsqueda exactamente con los criterios de filtrado del controlador
        products = self.env['product.product'].with_company(self.company_id).search([
            ('active', '=', True),
            ('sale_ok', '=', True),
            ('type', '=', 'product'),
            '|',
            ('company_id', '=', self.company_id.id),
            ('company_id', '=', False)
        ], limit=3)

        if not products:
            _logger.warning("[iCompras360 LOG] No se encontraron productos almacenables activos para la prueba.")
            return True

        # Invocamos al motor pasándole los registros de Odoo y la configuración actual
        exporter = IcomprasDataExporter(self.env, self)
        
        for product in products:
            try:
                linea_traza = exporter.generate_product_line(product)
                _logger.info("[iCompras360 LOG] Producto ID %s -> %s", product.id, linea_traza)
            except Exception as e:
                _logger.error("[iCompras360 LOG] Error procesando Producto ID %s: %s", product.id, str(e))

        _logger.info("[iCompras360 LOG] Fin de la simulación de Fase 2.")
        _logger.info("======================================================")
        return True