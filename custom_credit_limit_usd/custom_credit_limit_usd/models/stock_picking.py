from odoo import fields, models, _
from odoo.exceptions import UserError


class StockPicking(models.Model):
    _inherit = 'stock.picking'

    surtido_validado = fields.Boolean(
        string="Surtido Validado",
        default=False,
        copy=False,
        help="Indica si la persona autorizada o almacenista validó el surtido."
    )

    def action_validar_surtido(self):
        """Punto de control para que el almacenista o persona autorizada apruebe el surtido."""
        for picking in self:
            picking.surtido_validado = True
            picking.message_post(body=_("Surtido preventivo validado por %s.", self.env.user.name))



    def button_validate(self):
        """Bloquea la validación del movimiento si no ha sido surtido, salvo excepción multi-company."""
        for picking in self:
            is_multicompany_exception = self.env['ir.config_parameter'].sudo().get_param('custom_warehouse.multicompany_exception', False)

            if not is_multicompany_exception and not picking.surtido_validado:
                if picking.picking_type_id.code == 'outgoing':
                    raise UserError(_("No se puede validar el despacho sin antes realizar el control y validación de surtido."))

        res = super().button_validate()

        for picking in self:
            picking._notificar_roles_reabastecimiento()

        return res

    def _notificar_roles_reabastecimiento(self):
        """Notifica por el Chatter a los roles: Surtidor, Jefe de Almacén y Almacenista."""
        param_obj = self.env['ir.config_parameter'].sudo()

        surtidor_id = param_obj.get_param('custom_warehouse.surtidor_user_id')
        jefe_id = param_obj.get_param('custom_warehouse.jefe_almacen_user_id')
        almacenista_id = param_obj.get_param('custom_warehouse.almacenista_user_id')

        user_ids = [int(uid) for uid in [surtidor_id, jefe_id, almacenista_id] if uid]

        if user_ids:
            partners = self.env['res.users'].browse(user_ids).mapped('partner_id')
            self.message_post(
                body=_("Alerta de Reabastecimiento: Ingreso de nuevas existencias confirmado desde ubicación auxiliar."),
                partner_ids=partners.ids,
            )