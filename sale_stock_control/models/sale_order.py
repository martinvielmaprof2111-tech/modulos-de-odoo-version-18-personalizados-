from odoo import models, fields, api, _
from odoo.exceptions import UserError


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    def action_open_business_doc_catalog(self):
        res = super().action_open_business_doc_catalog()
        res['context'] = res.get('context', {})
        if self.warehouse_id:
            res['context']['warehouse'] = self.warehouse_id.id
        if self.pricelist_id:
            res['context']['pricelist'] = self.pricelist_id.id
        return res
        
    def _get_sale_allowed_locations(self, warehouse):
        if not warehouse:
            return []
        return self.env['stock.location'].search([
            ('usage', '=', 'internal'),
            ('company_id', '=', warehouse.company_id.id),
            '|',
            ('id', 'child_of', warehouse.lot_stock_id.id),
            ('allow_sale_stock', '=', True)
        ]).ids

    def action_confirm(self):
        for order in self:
            for line in order.order_line:
                if line.product_id and line.product_id.type == 'consu':
                    if line.free_qty < line.product_uom_qty:
                        raise UserError(
                            f"Estimado usuario, no es posible confirmar la orden.\n\n"
                            f"El producto '{line.product_id.display_name}' no cuenta con stock suficiente en el almacén '{order.warehouse_id.name}'.\n"
                            f"• Stock disponible en Almacén: {line.free_qty} {line.product_uom.name}\n"
                            f"• Cantidad requerida: {line.product_uom_qty} {line.product_uom.name}"
                        )
        return super().action_confirm()

    def _update_order_line_info(self, product_id, quantity, **kwargs):
        product = self.env['product.product'].browse(product_id)
        if product.type == 'consu' and quantity > 0:
            warehouse = self.warehouse_id
            allowed_loc_ids = self._get_sale_allowed_locations(warehouse)
            
            available_qty = 0.0
            if allowed_loc_ids:
                quants = self.env['stock.quant'].search([
                    ('location_id', 'in', allowed_loc_ids),
                    ('product_id', '=', product_id),
                    ('company_id', '=', self.company_id.id)
                ])
                available_qty = sum(quants.mapped('quantity')) - sum(quants.mapped('reserved_quantity'))

            if available_qty <= 0:
                lines = self.order_line.filtered(lambda l: l.product_id.id == product_id)
                if lines:
                    lines.unlink()
                raise UserError(
                    f"Estimado usuario, el producto '{product.display_name}' se encuentra SIN STOCK DISPONIBLE en el almacén {warehouse.name} (0 unidades libres)."
                )
            elif quantity > available_qty:
                raise UserError(
                    f"Estimado usuario, la cantidad seleccionada ({quantity}) supera el stock libre ({available_qty} unidades) en el almacén {warehouse.name} para '{product.display_name}'."
                )
        return super()._update_order_line_info(product_id, quantity, **kwargs)

    def _get_product_catalog_lines_data(self, parent_record=None, **kwargs):
        res = super()._get_product_catalog_lines_data(parent_record=parent_record, **kwargs)
        warehouse = self.warehouse_id
        warehouse_name = warehouse.name if warehouse else ''
        allowed_loc_ids = self._get_sale_allowed_locations(warehouse)

        # Usar la lista de precios asignada al pedido o buscar la de USD activa
        pricelist = self.pricelist_id
        usd_currency = self.env.ref('base.USD', raise_if_not_found=False) or self.company_id.currency_id

        # Optimización de stock mediante read_group
        product_ids = [int(p_id) for p_id in res.keys()]
        stock_data = {}
        if allowed_loc_ids and product_ids:
            quants = self.env['stock.quant'].read_group(
                [
                    ('location_id', 'in', allowed_loc_ids),
                    ('product_id', 'in', product_ids),
                    ('company_id', '=', self.company_id.id)
                ],
                ['product_id', 'quantity:sum', 'reserved_quantity:sum'],
                ['product_id']
            )
            for group in quants:
                p_id = group['product_id'][0]
                free = group['quantity'] - group['reserved_quantity']
                stock_data[p_id] = free

        # Iterar asignando datos al payload del Catálogo
        for product_id, data in res.items():
            pid_int = int(product_id)
            product_rec = self.env['product.product'].browse(pid_int)
            
            wh_free = stock_data.get(pid_int, 0.0)
            data['warehouse_name'] = warehouse_name
            data['free_qty'] = wh_free

            unit_price = 0.0

            # Búsqueda directa del ítem de regla en product.pricelist.item con fixed_price_usd
            if pricelist:
                item = self.env['product.pricelist.item'].search([
                    ('pricelist_id', '=', pricelist.id),
                    '|', ('product_id', '=', pid_int),
                    '&', ('product_tmpl_id', '=', product_rec.product_tmpl_id.id), ('product_id', '=', False)
                ], limit=1)

                if item and hasattr(item, 'fixed_price_usd') and item.fixed_price_usd:
                    unit_price = item.fixed_price_usd
                else:
                    unit_price = pricelist._get_product_price(product_rec, 1.0)
            else:
                unit_price = product_rec.lst_price

            data['usd_price'] = unit_price

        return res


class SaleOrderLine(models.Model):
    _inherit = 'sale.order.line'

    warehouse_id = fields.Many2one(
        related='order_id.warehouse_id',
        string='Almacén',
        readonly=True,
        store=True
    )

    free_qty = fields.Float(
        string='Stock Disp.',
        compute='_compute_warehouse_free_qty',
        readonly=True,
        store=False
    )

    @api.depends('product_id', 'order_id.warehouse_id')
    def _compute_warehouse_free_qty(self):
        for line in self:
            if line.product_id and line.order_id.warehouse_id:
                warehouse = line.order_id.warehouse_id
                allowed_loc_ids = line.order_id._get_sale_allowed_locations(warehouse)

                quants = self.env['stock.quant'].search([
                    ('location_id', 'in', allowed_loc_ids),
                    ('product_id', '=', line.product_id.id),
                    ('company_id', '=', line.order_id.company_id.id)
                ])
                total_qty = sum(quants.mapped('quantity'))
                reserved_qty = sum(quants.mapped('reserved_quantity'))
                line.free_qty = total_qty - reserved_qty
            else:
                line.free_qty = 0.0

    @api.onchange('product_id', 'product_uom_qty')
    def _check_stock_availability_onchange(self):
        if self.product_id and self.product_id.type == 'consu':
            if self.free_qty <= 0:
                self.product_id = False
                return {
                    'warning': {
                        'title': 'Producto sin Stock Real en Almacén',
                        'message': f'El producto seleccionado no tiene stock disponible en el almacén {self.order_id.warehouse_id.name} (0 unidades).'
                    }
                }
            elif self.product_uom_qty > self.free_qty:
                self.product_uom_qty = self.free_qty
                return {
                    'warning': {
                        'title': 'Cantidad sobrepasada',
                        'message': f'La cantidad supera el stock libre en el almacén {self.order_id.warehouse_id.name}. Ajustado automáticamente al máximo: {self.free_qty}.'
                    }
                }