from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    credit_limit_usd_default = fields.Float(
        string="Límite de crédito predeterminado (USD)",
        config_parameter='custom_credit_limit_usd.credit_limit_usd_default',
        help="Límite de crédito general en USD aplicable a los clientes sin límite específico.",
    )

    surtidor_user_id = fields.Many2one(
        'res.users',
        string="Surtidor Autorizado",
        config_parameter='custom_warehouse.surtidor_user_id',
    )
    jefe_almacen_user_id = fields.Many2one(
        'res.users',
        string="Jefe de Almacén",
        config_parameter='custom_warehouse.jefe_almacen_user_id',
    )
    almacenista_user_id = fields.Many2one(
        'res.users',
        string="Almacenista",
        config_parameter='custom_warehouse.almacenista_user_id',
    )
    multicompany_exception = fields.Boolean(
        string="Excepción Multi-Company (Surtido Automático)",
        config_parameter='custom_warehouse.multicompany_exception',
        help="Omite la validación manual de surtido en entornos multicompañía.",
    )