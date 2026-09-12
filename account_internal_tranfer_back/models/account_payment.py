# -*- coding: utf-8 -*-
import logging
from odoo import models, fields, api, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

class AccountPayment(models.Model):
    _inherit = 'account.payment'

    is_internal_transfer = fields.Boolean(
        string="Transferencia interna",
        default=False,
    )

    destination_journal_id = fields.Many2one(
        'account.journal', 
        string='Diario de destino', 
        domain="[('type', 'in', ('bank', 'cash')), ('id', '!=', journal_id)]"
    )

    def init(self):
        super(AccountPayment, self).init()
        
        view_name = 'account.payment.form.inherit.internal.transfer'
        existing_view = self.env['ir.ui.view'].search([
            ('name', '=', view_name),
            ('model', '=', 'account.payment')
        ], limit=1)
        
        arch_xml = """<data>
            <xpath expr="//field[@name='payment_type']" position="after">
                <field name="is_internal_transfer" readonly="state != 'draft'" invisible="state != 'draft' and not is_internal_transfer"/>
            </xpath>
            <xpath expr="//field[@name='partner_id']" position="attributes">
                <attribute name="invisible">is_internal_transfer</attribute>
                <attribute name="required">not is_internal_transfer</attribute>
            </xpath>
            <xpath expr="//field[@name='journal_id']" position="after">
                <field name="destination_journal_id" invisible="not is_internal_transfer" required="is_internal_transfer" readonly="state != 'draft'"/>
            </xpath>
        </data>"""
        
        if not existing_view:
            parent_view = self.env.ref('account.view_account_payment_form', raise_if_not_found=False)
            if parent_view:
                self.env['ir.ui.view'].create({
                    'name': view_name,
                    'model': 'account.payment',
                    'inherit_id': parent_view.id,
                    'arch': arch_xml,
                    'type': 'form',
                    'priority': 16,
                })
        else:
            existing_view.write({'arch': arch_xml})

    # =========================================================================
    # ACCIÓN DE PUBLICACIÓN: MULTIMONEDA & MULTI-COMPAÑÍA CORREGIDOS
    # =========================================================================

    def action_post(self):
        """ Interceptamos la confirmación para reestructurar el asiento origen,
            crear la contrapartida espejo respetando multi-compañía y multimoneda,
            y registrar las trazas en el chatter. """
        for payment in self:
            if payment.is_internal_transfer:
                if not payment.destination_journal_id:
                    raise UserError(_("Debe especificar un Diario de destino para poder realizar la transferencia interna."))
                
                payment.write({
                    'is_internal_transfer': True,
                    'partner_id': False,
                })

        try:
            # 1. Ejecución nativa del proceso de publicación de Odoo
            res = super(AccountPayment, self).action_post()
        except Exception as e:
            _logger.error("Error en super().action_post(): %s", str(e))
            raise UserError(_("Error procesando el asiento principal: %s") % str(e))

        # 2. Reestructuración de apuntes contables y generación del espejo correcto
        for payment in self:
            if payment.is_internal_transfer and payment.move_id:
                try:
                    origin_company = payment.company_id
                    target_company = payment.destination_journal_id.company_id or origin_company

                    # Cuentas puentes para origen y destino (Soporte Multi-Compañía)
                    origin_transfer_account = origin_company.transfer_account_id
                    target_transfer_account = target_company.transfer_account_id or origin_transfer_account

                    if not origin_transfer_account:
                        raise UserError(_("No se ha configurado la 'Cuenta de transferencias pendientes' en la compañía de origen."))

                    # Reestructuramos el asiento de origen
                    payment.move_id.button_draft()

                    corrected_lines = 0

                    if payment.payment_type == 'outbound':
                        puente_seq = 1
                        banco_seq = 100
                    else:
                        banco_seq = 1
                        puente_seq = 100

                    for line in payment.move_id.line_ids:
                        if line.account_id.account_type in ('asset_receivable', 'liability_payable'):
                            line.write({
                                'account_id': origin_transfer_account.id,
                                'sequence': puente_seq
                            })
                            corrected_lines += 1
                        else:
                            line.write({
                                'sequence': banco_seq
                            })

                    payment.move_id.action_post()

                    # --- CREACIÓN DEL ASIENTO ESPEJO (DESTINO) ---
                    destination_account = (
                        payment.destination_journal_id.default_account_id or 
                        payment.destination_journal_id.inbound_payment_method_line_ids.payment_account_id
                    )
                    
                    if not destination_account:
                        raise UserError(_("El diario de destino no tiene una cuenta contable configurada por defecto."))

                    # --- LÓGICA DE MULTIMONEDA PRECISA ---
                    target_company_currency = target_company.currency_id
                    payment_currency = payment.currency_id or origin_company.currency_id

                    # Calculamos el importe base (moneda de la compañía destino)
                    if payment_currency != target_company_currency:
                        company_amount = payment_currency._convert(
                            payment.amount,
                            target_company_currency,
                            target_company,
                            payment.date
                        )
                        foreign_currency_id = payment_currency.id
                        foreign_amount = payment.amount
                    else:
                        company_amount = payment.amount
                        foreign_currency_id = False
                        foreign_amount = 0.0

                    memo_text = payment.memo or _('Transferencia Interna')

                    # Estructuración de líneas según el tipo de pago
                    if payment.payment_type == 'outbound':
                        mirror_lines = [
                            (0, 0, {
                                'name': memo_text, 
                                'account_id': destination_account.id, 
                                'debit': company_amount, 
                                'credit': 0.0, 
                                'currency_id': foreign_currency_id,
                                'amount_currency': foreign_amount if foreign_currency_id else 0.0,
                                'sequence': 1
                            }),
                            (0, 0, {
                                'name': memo_text, 
                                'account_id': target_transfer_account.id, 
                                'debit': 0.0, 
                                'credit': company_amount, 
                                'currency_id': foreign_currency_id,
                                'amount_currency': -foreign_amount if foreign_currency_id else 0.0,
                                'sequence': 100
                            }),
                        ]
                    else:
                        mirror_lines = [
                            (0, 0, {
                                'name': memo_text, 
                                'account_id': target_transfer_account.id, 
                                'debit': company_amount, 
                                'credit': 0.0, 
                                'currency_id': foreign_currency_id,
                                'amount_currency': foreign_amount if foreign_currency_id else 0.0,
                                'sequence': 1
                            }),
                            (0, 0, {
                                'name': memo_text, 
                                'account_id': destination_account.id, 
                                'debit': 0.0, 
                                'credit': company_amount, 
                                'currency_id': foreign_currency_id,
                                'amount_currency': -foreign_amount if foreign_currency_id else 0.0,
                                'sequence': 100
                            }),
                        ]

                    move_vals = {
                        'date': payment.date,
                        'ref': memo_text,
                        'journal_id': payment.destination_journal_id.id,
                        'company_id': target_company.id,
                        'move_type': 'entry',
                        'line_ids': mirror_lines
                    }
                    
                    destination_move = self.env['account.move'].create(move_vals)
                    destination_move.action_post()

                    # --- ENLACES DINÁMICOS DE NAVEGACIÓN Y CHATTER ---
                    payment_url = f"/web#id={payment.id}&model=account.payment&view_type=form"
                    origin_move_url = f"/web#id={payment.move_id.id}&model=account.move&view_type=form"
                    destination_move_url = f"/web#id={destination_move.id}&model=account.move&view_type=form"

                    body_message_1 = "<div style='line-height: 1.5;'>"
                    if corrected_lines > 0:
                        body_message_1 += f"Cuenta actualizada a cuenta puente: <b>{origin_transfer_account.display_name}</b><br/>"
                    body_message_1 += f"Asiento de origen procesado: <a href='{origin_move_url}' target='_blank'><b>{payment.move_id.name}</b></a>"
                    body_message_1 += "</div>"

                    payment.message_post(
                        body=body_message_1,
                        message_type='comment',
                        subtype_xmlid='mail.mt_comment',
                        body_is_html=True
                    )

                    body_message_2 = (
                        f"<div style='line-height: 1.5;'>"
                        f"Contrapartida generada en diario destino.<br/>"
                        f"Asiento de destino vinculado: <a href='{destination_move_url}' target='_blank'><b>{destination_move.name}</b></a>"
                        f"</div>"
                    )

                    payment.message_post(
                        body=body_message_2,
                        message_type='comment',
                        subtype_xmlid='mail.mt_comment',
                        body_is_html=True
                    )

                    body_return_message = (
                        f"<div style='line-height: 1.5;'>"
                        f"Este asiento automático fue generado por una transferencia interna.<br/>"
                        f"Regresar al pago original: <a href='{payment_url}' target='_self'><b>{payment.name}</b></a>"
                        f"</div>"
                    )

                    destination_move.message_post(
                        body=body_return_message,
                        message_type='comment',
                        subtype_xmlid='mail.mt_comment',
                        body_is_html=True
                    )

                except Exception as ex:
                    _logger.error("Error crítico en la automatización del chatter/asiento: %s", str(ex))
                    payment.message_post(body=_("Error en Transferencia Interna: %s") % str(ex))
                    raise UserError(_("El proceso falló: %s") % str(ex))

        return res