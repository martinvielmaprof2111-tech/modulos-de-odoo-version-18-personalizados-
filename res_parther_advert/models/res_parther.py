import re
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError

class ResPartner(models.Model):
    _inherit = 'res.partner'

    def _get_only_digits(self, text_val):
        """ Extrae únicamente los caracteres numéricos de una cadena. """
        if not text_val:
            return ''
        return re.sub(r'\D', '', str(text_val))

    @api.constrains('identification_id', 'rif')
    def _check_unique_identification_and_rif(self):
        # Evitamos ejecutar validaciones si estamos en procesos automatizados de facturación o ventas
        # donde el partner no está editando su número de identificación/RIF.
        for partner in self:
            # Si el contexto viene de procesos transaccionales donde no se debe bloquear
            if self.env.context.get('skip_identification_check'):
                continue

            # 1. Auditoría sobre el campo identification_id
            if partner.identification_id:
                digits_ident = partner._get_only_digits(partner.identification_id)
                if digits_ident:
                    # Buscamos registros existentes (excluyendo al registro actual)
                    candidates = self.search([
                        ('id', '!=', partner.id),
                        ('identification_id', '!=', False)
                    ])
                    duplicate = candidates.filtered(
                        lambda p: partner._get_only_digits(p.identification_id) == digits_ident
                    )
                    if duplicate:
                        raise ValidationError(_(
                            '¡Atención! No se puede guardar el contacto. El Nro. de Cédula/Identificación ingresado '
                            'coincide numéricamente (%s) con el cliente ya registrado: "%s".'
                        ) % (digits_ident, duplicate[0].name))

            # 2. Auditoría sobre el campo rif
            if partner.rif:
                digits_rif = partner._get_only_digits(partner.rif)
                if digits_rif:
                    candidates = self.search([
                        ('id', '!=', partner.id),
                        ('rif', '!=', False)
                    ])
                    duplicate = candidates.filtered(
                        lambda p: partner._get_only_digits(p.rif) == digits_rif
                    )
                    if duplicate:
                        raise ValidationError(_(
                            '¡Atención! No se puede guardar el contacto. El RIF ingresado '
                            'coincide numéricamente (%s) con el cliente ya registrado: "%s".'
                        ) % (digits_rif, duplicate[0].name))

    @api.model_create_multi
    def create(self, vals_list):
        """ Captura la creación y audita únicamente si vienen campos de identificación """
        return super(ResPartner, self).create(vals_list)

    def write(self, vals):
        """ 
        Si la modificación del contacto viene desde facturación/ventas y NO altera 
        la cédula o el RIF, omitimos el constraint para no bloquear transacciones de clientes viejos duplicados.
        """
        if 'identification_id' not in vals and 'rif' not in vals:
            return super(ResPartner, self.with_context(skip_identification_check=True)).write(vals)
        return super(ResPartner, self).write(vals)