# -*- coding: utf-8 -*-

from odoo import models, fields, api
from odoo.exceptions import UserError
from odoo.addons.odoo_icompras_integration.utils.icompras_utils_importador import IcomprasDataImporter
from datetime import datetime, time
import logging
import pytz

_logger = logging.getLogger(__name__)


class IcomprasImportWizard(models.TransientModel):
    _name = 'icompras.import.wizard'
    _description = 'Asistente de Importación Masiva iCompras'

    @api.model
    def _get_default_date_start(self):
        user_tz = self.env.user.tz or 'UTC'
        local_tz = pytz.timezone(user_tz)
        today_local = datetime.now(local_tz).date()
        local_start = datetime.combine(today_local, time.min)
        local_start_dt = local_tz.localize(local_start)
        return local_start_dt.astimezone(pytz.utc).replace(tzinfo=None)

    @api.model
    def _get_default_date_end(self):
        user_tz = self.env.user.tz or 'UTC'
        local_tz = pytz.timezone(user_tz)
        today_local = datetime.now(local_tz).date()
        local_end = datetime.combine(today_local, time.max)
        local_end_dt = local_tz.localize(local_end)
        return local_end_dt.astimezone(pytz.utc).replace(tzinfo=None)

    date_start = fields.Datetime(
        string='Fecha Inicio',
        required=True,
        default=_get_default_date_start
    )
    date_end = fields.Datetime(
        string='Fecha Fin',
        required=True,
        default=_get_default_date_end
    )

    line_ids = fields.One2many(
        'icompras.import.wizard.line',
        'wizard_id',
        string='Pedidos Encontrados en iCompras'
    )

    def action_consultar_api(self):
        self.ensure_one()

        api_config = self.env['icompras.api.config'].search([
            ('company_id', '=', self.env.company.id),
            ('api_enabled', '=', True)
        ], limit=1)

        if not api_config:
            raise UserError("No se encontró ninguna configuración activa de iCompras para la compañía actual.")

        str_start = self.date_start.strftime('%Y-%m-%d %H:%M:%S')
        str_end = self.date_end.strftime('%Y-%m-%d %H:%M:%S')

        importer = IcomprasDataImporter(self.env)
        
        try:
            pedidos_encontrados = importer.consultar_pedidos_api(api_config, str_start, str_end)
        except Exception as e:
            _logger.error("!!! [ICOMPRAS ERROR] Excepción en consulta: %s", str(e))
            raise UserError(f"Error crítico al conectar con iCompras: {str(e)}")

        estado_previo_productos = {}

        for line in self.line_ids:
            for detail in line.detail_ids:
                clave_prod = (str(line.id_pedido_externo), detail.barcode)
                estado_previo_productos[clave_prod] = detail.selected

        self.line_ids.unlink()

        if not pedidos_encontrados:
            raise UserError("No se hallaron pedidos pendientes en iCompras para el rango seleccionado.")

        lineas_vals = []
        for ped in pedidos_encontrados:
            id_pedido = str(ped.get('id_pedido_externo'))
            lineas_articulos = ped.get('lineas_raw', [])

            cod_proveedor_externo = ped.get('cod_proveedor_externo', 'N/A')
            partner_res = self.env['res.partner'].search([
                ('ref', '=', cod_proveedor_externo),
                ('supplier_rank', '>', 0)
            ], limit=1)
            
            nombre_proveedor = partner_res.display_name if partner_res else f"Proveedor Ext. ({cod_proveedor_externo})"

            detail_vals = []
            monto_total_odoo = 0.0
            total_items = 0

            for item in lineas_articulos:
                raw_barcode = item.get('barra')
                barcode = str(raw_barcode).strip() if raw_barcode else None
                cantidad = int(item.get('cantidad', 0))

                if not barcode or cantidad <= 0:
                    continue

                product_res = self.env['product.product'].search([
                    ('barcode', '=', barcode),
                    ('company_id', 'in', [self.env.company.id, False])
                ], limit=1)

                if product_res:
                    precio_estandar = product_res.standard_price or product_res.lst_price
                    nombre_producto = product_res.display_name
                else:
                    precio_estandar = float(item.get('neto', 0.0))
                    nombre_producto = f"[NO ENCONTRADO EN ODOO] Barra: {barcode}"

                subtotal = cantidad * precio_estandar
                monto_total_odoo += subtotal
                total_items += cantidad

                clave_prod = (id_pedido, barcode)
                selected_producto = estado_previo_productos.get(clave_prod, True)

                detail_vals.append((0, 0, {
                    'selected': selected_producto,
                    'barcode': barcode,
                    'product_id': product_res.id if product_res else False,
                    'product_name': nombre_producto,
                    'cantidad': cantidad,
                    'precio_estandar': precio_estandar,
                    'subtotal': subtotal,
                }))

            lineas_vals.append((0, 0, {
                'id_pedido_externo': int(id_pedido) if id_pedido.isdigit() else id_pedido,
                'cod_proveedor_externo': cod_proveedor_externo,
                'nombre_proveedor': nombre_proveedor,
                'total_articulos': total_items,
                'monto_total': monto_total_odoo,
                'detail_ids': detail_vals
            }))

        self.write({'line_ids': lineas_vals})

        return {
            'name': 'Importar Pedidos iCompras',
            'type': 'ir.actions.act_window',
            'res_model': 'icompras.import.wizard',
            'view_mode': 'form',
            'res_id': self.id,
            'target': 'new',
        }

    def action_procesar_importacion(self):
        self.ensure_one()
        self.env.flush_all()

        mapa_pedidos_productos = {}
        for line in self.line_ids:
            detalles_seleccionados = line.detail_ids.filtered(lambda d: d.selected)
            if detalles_seleccionados:
                barcodes = [str(b).strip() for b in detalles_seleccionados.mapped('barcode') if b]
                if barcodes:
                    mapa_pedidos_productos[str(line.id_pedido_externo)] = barcodes

        _logger.info(">>> [ICOMPRAS IMPORT] Mapa dinámico preparado: %s", mapa_pedidos_productos)

        if not mapa_pedidos_productos:
            raise UserError("Debe seleccionar al menos un producto para importar.")

        api_config = self.env['icompras.api.config'].search([
            ('company_id', '=', self.env.company.id),
            ('api_enabled', '=', True)
        ], limit=1)

        if not api_config:
            raise UserError("No se encontró ninguna configuración activa de iCompras.")

        str_start = self.date_start.strftime('%Y-%m-%d %H:%M:%S')
        str_end = self.date_end.strftime('%Y-%m-%d %H:%M:%S')

        importer = IcomprasDataImporter(self.env)
        importer.import_sugeridos_api(
            api_config, 
            str_start, 
            str_end, 
            mapa_pedidos_productos=mapa_pedidos_productos
        )

        return {
            'name': 'Solicitudes de Presupuesto Creadas',
            'type': 'ir.actions.act_window',
            'res_model': 'purchase.order',
            'view_mode': 'list,form',
            'domain': [('origin', 'like', 'iCompras Pedido #')],
            'target': 'current',
        }

    def action_select_all_lines(self):
        self.ensure_one()
        for line in self.line_ids:
            for detail in line.detail_ids:
                detail.selected = True
        return self._reload_wizard()

    def action_deselect_all_lines(self):
        self.ensure_one()
        for line in self.line_ids:
            for detail in line.detail_ids:
                detail.selected = False
        return self._reload_wizard()

    def _reload_wizard(self):
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'icompras.import.wizard',
            'view_mode': 'form',
            'res_id': self.id,
            'target': 'new',
        }


class IcomprasImportWizardLine(models.TransientModel):
    _name = 'icompras.import.wizard.line'
    _description = 'Encabezado de Pedido iCompras'

    wizard_id = fields.Many2one('icompras.import.wizard', ondelete='cascade', string='Asistente Origen')
    
    id_pedido_externo = fields.Integer(string='ID Pedido (iCompras)', readonly=True)
    cod_proveedor_externo = fields.Char(string='Código Proveedor Ext.', readonly=True)
    nombre_proveedor = fields.Char(string='Proveedor (Odoo / Ext.)', readonly=True)
    total_articulos = fields.Integer(string='Total Productos', readonly=True)
    monto_total = fields.Float(string='Monto Estimado (Odoo)', readonly=True)

    filter_keyword = fields.Char(string='Filtrar Producto')

    detail_ids = fields.One2many(
        'icompras.import.wizard.line.detail',
        'wizard_line_id',
        string='Desglose de Productos'
    )

    progreso_seleccion = fields.Char(
        string='Seleccionados',
        compute='_compute_progreso_seleccion',
        store=False
    )

    @api.depends('detail_ids', 'detail_ids.selected')
    def _compute_progreso_seleccion(self):
        for rec in self:
            marcados = len(rec.detail_ids.filtered(lambda d: d.selected))
            totales = len(rec.detail_ids)
            rec.progreso_seleccion = f"{marcados} / {totales}"

    @api.onchange('filter_keyword')
    def _onchange_filter_keyword(self):
        for line in self.detail_ids:
            if not self.filter_keyword:
                line.is_visible = True
            else:
                kw = self.filter_keyword.lower().strip()
                match_barcode = line.barcode and kw in line.barcode.lower()
                match_name = line.product_name and kw in line.product_name.lower()
                line.is_visible = (match_barcode or match_name)

    def action_open_detail(self):
        self.ensure_one()
        self.filter_keyword = False
        for d in self.detail_ids:
            d.write({'is_visible': True})

        view_id = self.env.ref('odoo_icompras_integration.view_icompras_import_wizard_line_form').id
        return {
            'name': f'Desglose del Pedido #{self.id_pedido_externo}',
            'type': 'ir.actions.act_window',
            'res_model': 'icompras.import.wizard.line',
            'view_mode': 'form',
            'views': [(view_id, 'form')],
            'res_id': self.id,
            'target': 'new',
        }

    def action_select_all_details(self):
        self.ensure_one()
        for d in self.detail_ids:
            d.selected = True
        return self.action_open_detail()

    def action_deselect_all_details(self):
        self.ensure_one()
        for d in self.detail_ids:
            d.selected = False
        return self.action_open_detail()

    def action_save_and_return(self):
        self.ensure_one()
        return self.wizard_id._reload_wizard()


class IcomprasImportWizardLineDetail(models.TransientModel):
    _name = 'icompras.import.wizard.line.detail'
    _description = 'Detalle/Desglose de Productos iCompras'

    wizard_line_id = fields.Many2one('icompras.import.wizard.line', ondelete='cascade', string='Línea de Pedido')
    selected = fields.Boolean(string='Incluir', default=True)
    is_visible = fields.Boolean(string='Visible', default=True)
    barcode = fields.Char(string='Código de Barras', readonly=True)
    product_id = fields.Many2one('product.product', string='Producto Odoo', readonly=True)
    product_name = fields.Char(string='Nombre del Producto', readonly=True)
    cantidad = fields.Integer(string='Cantidad Solicitada', readonly=True)
    precio_estandar = fields.Float(string='Precio Estándar / Costo Odoo', readonly=True)
    subtotal = fields.Float(string='Subtotal Estimado', readonly=True)