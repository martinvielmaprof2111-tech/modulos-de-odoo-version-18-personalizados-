from odoo import models, fields, api, _
from odoo.exceptions import UserError

class StockPicking(models.Model):
    _inherit = 'stock.picking'

    @api.model_create_multi
    def create(self, vals_list):
        """Asigna correlativo único si el registro se crea en el contexto Multi Company Transfer."""
        for vals in vals_list:
            if vals.get('name', 'New') == 'New' and self.env.context.get('default_is_multi_company_transfer'):
                vals['name'] = self.env['ir.sequence'].next_by_code('multi.company.transfer.seq') or 'New'
        return super().create(vals_list)

    def button_validate(self):
        for picking in self:
            # Solo aplica validaciones de stock a ubicaciones internas de origen
            if picking.location_id and picking.location_id.usage == 'internal':
                unavailable_products = []

                for move in picking.move_ids:
                    if move.state in ('done', 'cancel'):
                        continue

                    # 1. Stock físico total en la ubicación origen
                    quants = self.env['stock.quant'].search([
                        ('location_id', 'child_of', picking.location_id.id),
                        ('product_id', '=', move.product_id.id),
                        ('company_id', '=', picking.company_id.id)
                    ])
                    total_physical = sum(quants.mapped('quantity'))
                    total_reserved = sum(quants.mapped('reserved_quantity'))

                    # Stock libre puro en quants
                    free_quant_stock = total_physical - total_reserved

                    # 2. Calcular demanda pendiente saliente (Ventas confirmadas no entregadas / Transferencias pendientes)
                    # Buscamos otros movimientos salientes desde la misma ubicación
                    pending_outgoing_moves = self.env['stock.move'].search([
                        ('location_id', 'child_of', picking.location_id.id),
                        ('product_id', '=', move.product_id.id),
                        ('company_id', '=', picking.company_id.id),
                        ('state', 'in', ('waiting', 'confirmed', 'assigned')),
                        ('id', '!=', move.id),  # Excluir el movimiento actual que se está validando
                        ('picking_id', '!=', picking.id)
                    ])
                    
                    # Sumamos la cantidad pendiente que aún no ha reservado quant pero ya está comprometida
                    unreserved_pending_qty = 0.0
                    for pending_move in pending_outgoing_moves:
                        # Si el movimiento pendiente no tiene reserva completa, calculamos lo comprometido no reservado
                        reserved_in_move = sum(pending_move.move_line_ids.mapped('quantity_product_uom')) if pending_move.move_line_ids else 0.0
                        needed_in_move = pending_move.product_uom_qty
                        if needed_in_move > reserved_in_move:
                            unreserved_pending_qty += (needed_in_move - reserved_in_move)

                    # 3. Stock verdaderamente libre para Multi Company Transfer
                    real_available_stock = free_quant_stock - unreserved_pending_qty

                    # Si el picking actual ya tiene reserva en move_line_ids, la tomamos a favor
                    qty_reserved_for_this_move = sum(move.move_line_ids.mapped('quantity_product_uom')) if move.move_line_ids else 0.0
                    effective_available = real_available_stock + qty_reserved_for_this_move

                    if effective_available < move.product_uom_qty:
                        unavailable_products.append(
                            f"• <b>{move.product_id.display_name}</b><br/>"
                            f"  - Requerido para la transferencia: {move.product_uom_qty:.2f}<br/>"
                            f"  - Stock Físico: {total_physical:.2f}<br/>"
                            f"  - Reservado / Comprometido en Ventas u otras entregas: {(total_physical - effective_available):.2f}<br/>"
                            f"  - <b>Disponible Real para Transferir: {max(0.0, effective_available):.2f}</b>"
                        )

                if unavailable_products:
                    products_list = "<br/><br/>".join(unavailable_products)
                    raise UserError(
                        _("No se puede validar la transferencia intercompañía. Hay stock comprometido en ventas u otras operaciones desde la ubicación '%s':<br/><br/>%s")
                        % (picking.location_id.display_name, products_list)
                    )

        return super().button_validate()