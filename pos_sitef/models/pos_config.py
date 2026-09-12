# -*- coding: utf-8 -*-
from odoo import fields, models, api

class PosConfig(models.Model):
    _inherit = 'pos.config'

    # Credenciales globales centralizadas con valores por defecto
    sitef_vuelto_client_id = fields.Char(string="Vuelto: Client ID", default='244ddca2')
    sitef_vuelto_client_secret = fields.Char(string="Vuelto: Client Secret", default='145242edbd31d772adec3e264a262a82')
    
    sitef_consulta_client_id = fields.Char(string="Consultas: Client ID", default='C76b7cbc')
    sitef_consulta_client_secret = fields.Char(string="Consultas: Client Secret", default='b4e883efd9b5dd0dfbdcaa7f05c81c72')
    
    # Parámetros de identidad física (ajusta el default según tu sede/caja base)
    sitef_id_sede = fields.Integer(string="ID de Sede (idbranch)", default=0)
    sitef_codigo_caja = fields.Char(string="Código de Caja (codestall)", default='001')
    
    # Direccionamiento de red hacia el microservicio local
    sitef_merchant_ip = fields.Char(string="IP del Merchant", default="127.0.0.1")
    sitef_merchant_puerto = fields.Char(string="Puerto Merchant", default="5000")

    sitef_usuario_local = fields.Char(string="Usuario Terminal", default="FarmaciaBallenaC1")
    sitef_password_local = fields.Char(string="Contraseña Terminal", default="d1d74fd3fa96bfd7b0ff460a9f8e2f57")

    @api.model
    def _get_pos_data_fields(self, config_id):
        """
        Serializa los campos para que estén disponibles en el frontend del POS.
        """
        res = super()._get_pos_data_fields(config_id)
        res.extend([
            'sitef_vuelto_client_id', 
            'sitef_vuelto_client_secret',
            'sitef_consulta_client_id', 
            'sitef_consulta_client_secret',
            'sitef_id_sede', 
            'sitef_codigo_caja',
            'sitef_merchant_ip', 
            'sitef_merchant_puerto', 
            'sitef_usuario_local',
            'sitef_password_local',
            'tax_today'
        ])
        return res

class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    # Campos relacionados para permitir la edición desde la vista de Ajustes Generales
    sitef_vuelto_client_id = fields.Char(related='pos_config_id.sitef_vuelto_client_id', readonly=False)
    sitef_vuelto_client_secret = fields.Char(related='pos_config_id.sitef_vuelto_client_secret', readonly=False)
    sitef_consulta_client_id = fields.Char(related='pos_config_id.sitef_consulta_client_id', readonly=False)
    sitef_consulta_client_secret = fields.Char(related='pos_config_id.sitef_consulta_client_secret', readonly=False)
    sitef_id_sede = fields.Integer(related='pos_config_id.sitef_id_sede', readonly=False)
    sitef_codigo_caja = fields.Char(related='pos_config_id.sitef_codigo_caja', readonly=False)
    sitef_merchant_ip = fields.Char(related='pos_config_id.sitef_merchant_ip', readonly=False)
    sitef_merchant_puerto = fields.Char(related='pos_config_id.sitef_merchant_puerto', readonly=False)

    sitef_usuario_local = fields.Char(related='pos_config_id.sitef_usuario_local', readonly=False)
    sitef_password_local = fields.Char(related='pos_config_id.sitef_password_local', readonly=False)