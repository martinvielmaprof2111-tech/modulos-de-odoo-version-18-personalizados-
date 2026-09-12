from odoo import models, fields, api


class ProductProduct(models.Model):
    _inherit = 'product.product'

    free_qty = fields.Float(
        string='Stock Real Libre',
        compute='_compute_free_qty',
        search='_search_free_qty'
    )
    usd_price = fields.Monetary(
        related='product_tmpl_id.usd_price',
        string='Precio USD',
        currency_field='usd_currency_id'
    )
    usd_currency_id = fields.Many2one(
        related='product_tmpl_id.usd_currency_id'
    )

    def _compute_free_qty(self):
        warehouse_id = self.env.context.get('warehouse') or self.env.context.get('warehouse_id')
        if warehouse_id:
            warehouse = self.env['stock.warehouse'].browse(warehouse_id)
        else:
            warehouse = self.env['stock.warehouse'].search([('company_id', '=', self.env.company.id)], limit=1)

        allowed_loc_ids = []
        if warehouse:
            allowed_loc_ids = self.env['stock.location'].search([
                ('usage', '=', 'internal'),
                ('company_id', '=', warehouse.company_id.id),
                '|',
                ('id', 'child_of', warehouse.lot_stock_id.id),
                ('allow_sale_stock', '=', True)
            ]).ids

        for product in self:
            if allowed_loc_ids:
                quants = self.env['stock.quant'].search([
                    ('location_id', 'in', allowed_loc_ids),
                    ('product_id', '=', product.id),
                    ('company_id', '=', self.env.company.id)
                ])
                total_qty = sum(quants.mapped('quantity'))
                reserved_qty = sum(quants.mapped('reserved_quantity'))
                product.free_qty = total_qty - reserved_qty
            else:
                product.free_qty = 0.0

    def _search_free_qty(self, operator, value):
        return [('qty_available', operator, value)]


class ProductTemplate(models.Model):
    _inherit = 'product.template'

    free_qty = fields.Float(
        string='Stock Real Libre',
        compute='_compute_free_qty',
        search='_search_free_qty'
    )
    usd_price = fields.Monetary(
        string='Precio USD',
        compute='_compute_usd_price',
        currency_field='usd_currency_id'
    )
    usd_currency_id = fields.Many2one(
        'res.currency',
        compute='_compute_usd_currency_id'
    )

    @api.depends('product_variant_ids.free_qty')
    def _compute_free_qty(self):
        for template in self:
            template.free_qty = sum(template.product_variant_ids.mapped('free_qty'))

    def _search_free_qty(self, operator, value):
        return [('product_variant_ids.free_qty', operator, value)]

    @api.depends_context('company')
    def _compute_usd_currency_id(self):
        usd = self.env.ref('base.USD', raise_if_not_found=False)
        for rec in self:
            rec.usd_currency_id = usd or rec.company_id.currency_id

    def _compute_usd_price(self):
        usd = self.env.ref('base.USD', raise_if_not_found=False)
        
        # 1. Obtener la lista de precios activa desde el contexto o usar la primera disponible de la empresa
        pricelist_id = self.env.context.get('pricelist')
        if pricelist_id:
            pricelist = self.env['product.pricelist'].browse(pricelist_id)
        else:
            pricelist = self.env['product.pricelist'].search([
                ('company_id', 'in', [self.env.company.id, False])
            ], limit=1)

        for template in self:
            price_found = False

            # 2. Buscar si la plantilla tiene una regla con fixed_price_usd en la lista de precios activa
            if pricelist:
                item = self.env['product.pricelist.item'].search([
                    ('pricelist_id', '=', pricelist.id),
                    '|', ('product_tmpl_id', '=', template.id),
                    ('product_id', 'in', template.product_variant_ids.ids)
                ], limit=1)

                if item and hasattr(item, 'fixed_price_usd') and item.fixed_price_usd:
                    template.usd_price = item.fixed_price_usd
                    price_found = True

            # 3. Fallback: Si no hay regla específica en la lista, convertir list_price
            if not price_found:
                if usd and template.currency_id:
                    template.usd_price = template.currency_id._convert(
                        template.list_price,
                        usd,
                        template.env.company,
                        fields.Date.today()
                    )
                else:
                    template.usd_price = template.list_price