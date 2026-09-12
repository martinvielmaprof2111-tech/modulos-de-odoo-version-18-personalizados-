# -*- coding: utf-8 -*-

from odoo import models, fields, api
from odoo.exceptions import UserError
from odoo.addons.odoo_icompras_integration.utils.icompras_utils_importador import IcomprasDataImporter
from datetime import datetime

class IcomprasApiConfig(models.Model):
    _name = 'icompras.api.config'
    _description = 'Configuracion de API de Entrada - iCompras'
    _check_company_domain = True

    name = fields.Char(
        string='Descripcion', 
        required=True, 
        default='Configuracion API Sugeridos'
    )
    company_id = fields.Many2one(
        'res.company', 
        string='Farmacia / Compania', 
        required=True, 
        default=lambda self: self.env.company
    )
    api_url_base = fields.Char(
        string='URL Base de la API', 
        required=True, 
        help='Ejemplo: https://api.icompras360.com/api'
    )
    api_email = fields.Char(
        string='Correo de Usuario (API)', 
        required=True, 
        help='Ejemplo: farmacialasballenas2024@gmail.com'
    )
    api_password = fields.Char(
        string='Contrasena (API)', 
        required=True
    )
    api_enabled = fields.Boolean(
        string='API Activa', 
        default=True
    )

    _sql_constraints = [
        ('company_uniq', 'unique (company_id)', '¡Ya existe una configuracion de API para esta farmacia!')
    ]

    def action_import_sugeridos_manual(self):
        """
        Metodo disparado por el boton de la vista XML para realizar
        una ejecucion de prueba controlada utilizando las fechas del dia de hoy.
        """
        self.ensure_one()
        importer = IcomprasDataImporter(self.env)
        
        fecha_hoy = datetime.today().strftime('%Y-%m-%d')
        date_start = f"{fecha_hoy} 00:00:00"
        date_end = f"{fecha_hoy} 23:59:59"
        
        # En ejecuciones masivas o manuales de prueba pasamos vacíos los IDs temporales ya que procesa directo
        resultado = importer.import_sugeridos_api(self, date_start, date_end)
        
        if resultado:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'Importación Exitosa',
                    'message': 'Se ha consumido la API e inyectado las Órdenes de Compra correctamente.',
                    'type': 'success',
                    'sticky': False,
                }
            }
        else:
            raise UserError("No se pudieron procesar los sugeridos de la API para el día de hoy. Verifique las credenciales o el historial de errores.")


class IcomprasLogError(models.Model):
    _name = 'icompras.log.error'
    _description = 'Historial de Errores de Integración iCompras'
    _order = 'create_date desc'

    name = fields.Char(
        string='Resumen del Error', 
        required=True
    )
    error_type = fields.Selection([
        ('api', 'Error de la API / Respuesta Externa'),
        ('connection', 'Fallo de Conexión / Tiempo de Espera'),
        ('odoo', 'Fallo Interno de Odoo / Validación ORM'),
        ('data', 'Inconsistencia de Datos (Productos/Proveedores Faltantes)')
    ], string='Tipo de Error', required=True, default='api')
    
    company_id = fields.Many2one(
        'res.company', 
        string='Farmacia', 
        default=lambda self: self.env.company
    )
    technical_details = fields.Text(
        string='Detalles Técnicos / Stack Trace'
    )