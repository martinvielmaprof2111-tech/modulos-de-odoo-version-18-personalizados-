# -*- coding: utf-8 -*-

import requests
import logging
from odoo import fields

_logger = logging.getLogger(__name__)


class IcomprasDataImporter:
    def __init__(self, env):
        self.env = env

    def _generate_unique_rif(self, cod_proveedor):
        if not cod_proveedor or cod_proveedor == 'N/A':
            return "J-00000000-0"
        hash_num = sum(ord(char) * (idx + 1) for idx, char in enumerate(str(cod_proveedor)))
        base_rif = str(10000000 + (hash_num % 89999999))
        return f"J-{base_rif}-0"

    def _force_venezuelan_fiscal_data_direct_sql(self, partner_id, cod_proveedor_externo):
        generated_rif = self._generate_unique_rif(cod_proveedor_externo)
        cr = self.env.cr

        cr.execute("SELECT column_name FROM information_schema.columns WHERE table_name='res_partner'")
        campos_totales = [row[0] for row in cr.fetchall()]
        
        try:
            rif_limpio = generated_rif.replace("-", "").upper()
            rif_formateado = generated_rif.upper()
            
            cr.execute("""
                UPDATE res_partner 
                SET vat = %s, 
                    identification_id = %s,
                    supplier_rank = COALESCE(supplier_rank, 0) + 1 
                WHERE id = %s
            """, (rif_limpio, rif_limpio, partner_id))

            if 'x_rif' in campos_totales:
                cr.execute("UPDATE res_partner SET x_rif = %s WHERE id = %s", (rif_formateado, partner_id))
            
            if 'rif' in campos_totales:
                cr.execute("UPDATE res_partner SET rif = %s WHERE id = %s", (rif_formateado, partner_id))

            identificacion_id = False
            if 'l10n_latam.identification.type' in self.env:
                tipo_doc = self.env['l10n_latam.identification.type'].search([
                    ('name', 'ilike', 'RIF'), 
                    ('country_id.code', '=', 'VE')
                ], limit=1)
                if not tipo_doc:
                    tipo_doc = self.env['l10n_latam.identification.type'].search([('name', 'ilike', 'RIF')], limit=1)
                if tipo_doc:
                    identificacion_id = tipo_doc.id

            if 'l10n_latam_identification_type_id' in campos_totales and identificacion_id:
                cr.execute("UPDATE res_partner SET l10n_latam_identification_type_id = %s WHERE id = %s", (identificacion_id, partner_id))

            if 'l10n_ve_document_type' in campos_totales:
                cr.execute("UPDATE res_partner SET l10n_ve_document_type = 'rif' WHERE id = %s", (partner_id,))
            if 'l10n_ve_person_type' in campos_totales:
                cr.execute("UPDATE res_partner SET l10n_ve_person_type = 'pjdo' WHERE id = %s", (partner_id,))
            if 'l10n_ve_responsibility_type_id' in campos_totales:
                resp_type = self.env['l10n_ve.responsibility.type'].search([], limit=1)
                if resp_type:
                    cr.execute("UPDATE res_partner SET l10n_ve_responsibility_type_id = %s WHERE id = %s", (resp_type.id, partner_id))

            partner_record = self.env['res.partner'].browse(partner_id)
            if hasattr(partner_record, 'invalidate_recordset'):
                partner_record.invalidate_recordset()
            elif hasattr(self.env, 'invalidate_all'):
                self.env.invalidate_all()
            
            if hasattr(self.env, 'flush_all'):
                self.env.flush_all()

        except Exception as sql_err:
            _logger.error("❌ [SQL_FISCAL_ERROR] Partner ID: %s | Error: %s", partner_id, str(sql_err))

    def consultar_pedidos_api(self, api_config_record, date_start, date_end):
        if not api_config_record or not api_config_record.api_enabled:
            return []

        url = api_config_record.api_url_base.strip()
        params = {
            'email': api_config_record.api_email,
            'password': api_config_record.api_password,
            'start_date': date_start,
            'end_date': date_end,
            'groupByOdc': 1,
            'type': 'N'
        }
        headers = {'User-Agent': 'OdooicomprasIntegration/1.0', 'Accept': '*/*'}

        try:
            response = requests.get(url, params=params, headers=headers, timeout=30)
            if response.status_code != 200:
                return []
            json_data = response.json()
            if json_data.get('status') == 'error' or 'result' not in json_data or not json_data['result']:
                return []

            pedidos_lista = []
            for pedido in json_data['result']:
                id_pedido = pedido.get('idpedido')
                lineas = pedido.get('data', [])
                if not id_pedido:
                    continue

                cod_proveedor = pedido.get('codprove') or (lineas[0].get('codprove', 'N/A') if lineas else 'N/A')

                pedidos_lista.append({
                    'id_pedido_externo': id_pedido,
                    'cod_proveedor_externo': cod_proveedor,
                    'lineas_raw': lineas
                })
            return pedidos_lista
        except Exception as e:
            _logger.error("💥 [API_GET_ERROR] Error en consulta base: %s", str(e))
            return []

    def import_sugeridos_api(self, api_config_record, date_start, date_end, mapa_pedidos_productos=None):
        if not api_config_record or not api_config_record.api_enabled:
            return False

        url = api_config_record.api_url_base.strip()
        params = {
            'email': api_config_record.api_email,
            'password': api_config_record.api_password,
            'start_date': date_start,
            'end_date': date_end,
            'groupByOdc': 1,
            'type': 'N'
        }
        headers = {'User-Agent': 'OdooicomprasIntegration/1.0', 'Accept': '*/*'}

        try:
            response = requests.get(url, params=params, headers=headers, timeout=30)
            if response.status_code != 200:
                return False
                
            json_data = response.json()
            if 'result' not in json_data or not json_data['result']:
                return False

            pedidos_procesados = []

            for pedido in json_data['result']:
                id_pedido_externo = str(pedido.get('idpedido'))
                lineas_articulos = pedido.get('data', [])
                
                if not id_pedido_externo or id_pedido_externo == 'None':
                    continue

                # Filtrar solo pedidos seleccionados por el cliente
                if mapa_pedidos_productos is not None and id_pedido_externo not in mapa_pedidos_productos:
                    continue

                origen_buscado = f"iCompras Pedido #{id_pedido_externo}"
                po_existente = self.env['purchase.order'].search([
                    ('origin', '=', origen_buscado),
                    ('company_id', '=', api_config_record.company_id.id)
                ], limit=1)

                if po_existente:
                    _logger.info("⏭️ [ANTI_DUPLICATE_SKIP] El pedido #%s ya existe como: %s", id_pedido_externo, po_existente.name)
                    continue

                barcodes_permitidos_pedido = mapa_pedidos_productos.get(id_pedido_externo, []) if mapa_pedidos_productos else []

                productos_por_proveedor = {}

                for item in lineas_articulos:
                    raw_barcode = item.get('barra')
                    barcode = str(raw_barcode).strip() if raw_barcode else None
                    cantidad = int(item.get('cantidad', 0))
                    cod_proveedor_externo = item.get('codprove') or pedido.get('codprove')

                    if not barcode or cantidad <= 0:
                        continue

                    # Filtrar solo productos con check activo
                    if mapa_pedidos_productos is not None and barcode not in barcodes_permitidos_pedido:
                        continue

                    product_res = self.env['product.product'].search([
                        ('barcode', '=', barcode),
                        ('company_id', 'in', [api_config_record.company_id.id, False])
                    ], limit=1)

                    if not product_res:
                        _logger.warning("❌ [READ_NOT_FOUND] Pedido: %s | Barra: %s", id_pedido_externo, barcode)
                        continue

                    precio_estandar_odoo = product_res.standard_price or product_res.lst_price

                    partner_res = self.env['res.partner'].search([
                        ('ref', '=', cod_proveedor_externo),
                        ('supplier_rank', '>', 0)
                    ], limit=1)

                    if not partner_res and cod_proveedor_externo and cod_proveedor_externo != 'N/A':
                        try:
                            partner_res = self.env['res.partner'].create({
                                'name': f"Proveedor iCompras {cod_proveedor_externo}",
                                'ref': cod_proveedor_externo,
                                'company_id': api_config_record.company_id.id,
                                'is_company': True,
                                'company_type': 'company',
                                'street': 'Dirección iCompras',
                            })
                        except Exception as partner_err:
                            _logger.error("❌ [PARTNER_CREATE_ERR] Proveedor: %s | Error: %s", cod_proveedor_externo, str(partner_err))
                            continue

                    if not partner_res:
                        continue

                    self._force_venezuelan_fiscal_data_direct_sql(partner_res.id, cod_proveedor_externo)

                    if partner_res.id not in productos_por_proveedor:
                        productos_por_proveedor[partner_res.id] = []

                    productos_por_proveedor[partner_res.id].append({
                        'product_id': product_res.id,
                        'product_qty': cantidad,
                        'price_unit': precio_estandar_odoo,
                        'name': product_res.display_name,
                        'product_uom': product_res.uom_po_id.id or product_res.uom_id.id
                    })

                if productos_por_proveedor:
                    exito_creacion = self._create_purchase_orders(
                        productos_por_proveedor, 
                        id_pedido_externo, 
                        api_config_record.company_id.id
                    )
                    if exito_creacion:
                        pedidos_procesados.append(id_pedido_externo)

            return True

        except Exception as e:
            _logger.error("💥 [CRITICAL_IMPORT_ERROR] Detalle: %s", str(e))
            return False

    def _create_purchase_orders(self, agrupacion_proveedores, id_pedido_externo, company_id):
        picking_type = self.env['stock.picking.type'].search([('code', '=', 'incoming'), ('company_id', '=', company_id)], limit=1)
        picking_type_id = picking_type.id if picking_type else False

        for partner_id, lineas in agrupacion_proveedores.items():
            po_vals = {
                'partner_id': partner_id,
                'company_id': company_id,
                'date_order': fields.Datetime.now(),
                'origin': f"iCompras Pedido #{id_pedido_externo}",
                'order_line': []
            }

            if picking_type_id:
                po_vals['picking_type_id'] = picking_type_id

            for line in lineas:
                po_vals['order_line'].append((0, 0, {
                    'product_id': line['product_id'],
                    'product_qty': line['product_qty'],
                    'price_unit': line['price_unit'],
                    'name': line['name'],
                    'product_uom': line['product_uom'],
                    'date_planned': fields.Datetime.now(),
                }))

            try:
                self.env['purchase.order'].create(po_vals)
            except Exception as po_err:
                _logger.error("❌ [PO_CREATE_ERR] Pedido: %s | Partner: %s | Error: %s", id_pedido_externo, partner_id, str(po_err))
                return False

        return True