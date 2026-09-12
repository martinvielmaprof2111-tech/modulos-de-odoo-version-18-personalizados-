# -*- coding: utf-8 -*-

import re
from datetime import datetime

class IcomprasDataExporter:
    def __init__(self, env, config_record):
        self.env = env
        self.config = config_record

    def sanitize_text(self, text):
        """
        Limpia cadenas de texto de caracteres acentuados, saltos de línea 
        y el delimitador prohibido tubería '|'.
        """
        if not text:
            return "N/A"
        
        # Convertir a string por seguridad
        text = str(text)
        
        # Diccionario de sustitución de acentos y caracteres especiales latinos
        replacements = {
            'á': 'a', 'é': 'e', 'í': 'i', 'ó': 'o', 'ú': 'u',
            'Á': 'A', 'É': 'E', 'Í': 'I', 'Ó': 'O', 'Ú': 'U',
            'ñ': 'n', 'Ñ': 'N', 'ü': 'u', 'Ü': 'U'
        }
        for orig, rep in replacements.items():
            text = text.replace(orig, rep)
        
        # Remover saltos de línea, retornos de carro y el caracter de tubería '|'
        text = text.replace('\n', ' ').replace('\r', ' ').replace('|', ' ')
        
        # Eliminar cualquier otro símbolo especial no deseado conservando letras, números y espacios
        text = re.sub(r'[@#%]', '', text)
        
        return text.strip().upper()

    def format_decimal(self, value, decimals=2):
        """
        Formatea valores numéricos asegurando el uso del punto '.' como decimal 
        y omitiendo separadores de miles.
        """
        if not value:
            return "0.00" if decimals == 2 else "0.0000"
        try:
            float_val = float(value)
            if decimals == 4:
                return f"{float_val:.4f}"
            return f"{float_val:.2f}"
        except (ValueError, TypeError):
            return "0.00" if decimals == 2 else "0.0000"

    def generate_product_line(self, product):
        """
        Mapea y concatena secuencialmente los 41 campos del producto delimitados por '|'.
        """
        # Fecha actual del catálogo formateada de manera estricta
        fecha_actual = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        # --- Extracción de Campos desde el ORM de Odoo 18 ---
        
        # 0 -> sBarra: Código de barras o en su defecto la referencia interna
        sBarra = self.sanitize_text(product.barcode or product.default_code or '0')
        
        # 1 -> sCodprod: Código único interno en Odoo
        raw_id = getattr(product, 'id', None) or (product.get('id') if isinstance(product, dict) else None)
        if not raw_id and product.default_code:
            raw_id = product.default_code
        sCodprod = self.sanitize_text(str(raw_id or '0'))
        
        # 2 -> sDesprod: Nombre comercial del producto libre de acentos
        sDesprod = self.sanitize_text(product.name)
        
        # 3 -> sTipo: M para Medicinas, C para Misceláneos. Determinación por tipo de producto/categoría
        sTipo = "M" if "MEDIC" in self.sanitize_text(product.categ_id.name) else "C"
        
        # 4 -> sIva: Porcentaje del impuesto aplicable (Ej: 16.00 o 0.00)
        taxes = product.taxes_id.filtered(lambda t: t.amount_type == 'percent')
        sIva = self.format_decimal(taxes[0].amount if taxes else 0.00)
        
        # 5 -> sRegulado: Por defecto 'N'
        sRegulado = "N"
        
        # 6 -> sCodprov: Valor por defecto '0'
        sCodprov = "0"
        
        # 7 -> sPrecio1: Precio de venta al público neto (Sin IVA)
        sPrecio1 = self.format_decimal(product.lst_price)
        
        # 8 -> sCantidad: Stock físico real disponible "A la mano" en Odoo
        sCantidad = str(int(product.qty_available))
        
        # 9 -> sOriginal: Unidad de manejo básica, por defecto '1'
        sOriginal = "1"
        
        # 10 -> sDa: Porcentaje de descuento, por defecto '0.00'
        sDa = "0.00"
        
        # 11 -> sOferta: Valor por defecto '0.00'
        sOferta = "0.00"
        
        # 12 -> sUpre: Valor por defecto '0'
        sUpre = "0"
        
        # 13 -> sPpre: Valor por defecto '0.00'
        sPpre = "0.00"
        
        # 14 -> sPsugerido: Mapeado al precio regular de venta
        sPsugerido = sPrecio1
        
        # 15 -> sPgris: Valor por defecto '0.00'
        sPgris = "0.00"
        
        # 16 -> sNuevo: Valor por defecto '0'
        sNuevo = "0"
        
        # 17 -> sFechafalla: Fecha de última actualización de costos o creación, en formato estricto
        sFechafalla = product.write_date.strftime("%Y-%m-%d %H:%M:%S") if product.write_date else fecha_actual
        
        # 18 -> sTipocatalogo: Valor por defecto 'PRINCIPAL'
        sTipocatalogo = "PRINCIPAL"
        
        # 19 -> sCuarentena: Valor por defecto '0'
        sCuarentena = "0"
        
        # 20 -> sDctoneto: Valor por defecto '0.00'
        sDctoneto = "0.00"
        
        # 21 -> sLote: Se puede recuperar si Odoo maneja lotes, por defecto un marcador genérico '0'
        sLote = "0"
        
        # 22 -> sFecvence: Fecha vencimiento del lote o marcador lejano si no aplica
        sFecvence = "2030-12-31 00:00:00"
        
        # 23 -> sMarcamodelo: Fabricante o marca del producto (Atributo de Odoo o campo personalizado)
        sMarcamodelo = self.sanitize_text(product.product_tmpl_id.seller_ids[0].name.name) if product.product_tmpl_id.seller_ids else "N/A"
        
        # 24 -> sPactivo: Principio activo (Se mapea desde campos de descripción o la misma categoría)
        sPactivo = self.sanitize_text(product.description_sale or "N/A")
        
        # 25 -> sCosto: Último costo estándar de adquisición registrado en la ficha del producto
        sCosto = self.format_decimal(product.standard_price)
        
        # 26 -> sUbicacion: Ubicación en estante de almacén
        sUbicacion = "N/A"
        
        # 27 -> sDescorta: Nombre corto del artículo
        sDescorta = self.sanitize_text(product.name[:20] if product.name else "N/A")
        
        # 28 -> sCodisb: RIF de la farmacia configurado en la interfaz de la Fase 1
        sCodisb = self.sanitize_text(self.config.cod_isb)
        
        # 29 -> sFeccatalogo: Fecha y hora exacta de la generación de la respuesta
        sFeccatalogo = fecha_actual
        
        # 30 -> sDepartamento: Nombre de la categoría raíz del producto
        sDepartamento = self.sanitize_text(product.categ_id.name)
        
        # 31 -> sGrupo: Clasificación intermedia, por defecto 'N/A'
        sGrupo = "N/A"
        
        # 32 -> sSubgrupo: Clasificación menor, por defecto 'N/A'
        sSubgrupo = "N/A"
        
        # 33 -> sOpc1: Identificador numérico de la categoría en Odoo
        sOpc1 = str(product.categ_id.id).zfill(5)
        
        # 34 -> sOpc2: Marcador por defecto 'N/A'
        sOpc2 = "N/A"
        
        # 35 -> sOpc3: Marcador por defecto 'N/A'
        sOpc3 = "N/A"
        
        # 36 a 39 -> sPrecio2 al sPrecio5: Listas alternativas de precios en Odoo (Relleno a 0.00)
        sPrecio2 = "0.00"
        sPrecio3 = "0.00"
        sPrecio4 = "0.00"
        sPrecio5 = "0.00"
        
        # 40 -> sVmd: Venta Media Diaria. Exige por documentación tener estrictamente 4 decimales
        sVmd = self.format_decimal(0.0000, decimals=4)

        # --- Ensamble Final de la Fila ---
        # Unimos las 41 variables posicionales utilizando el separador de tuberías '|'
        linea_completa = (
            f"{sBarra}|{sCodprod}|{sDesprod}|{sTipo}|{sIva}|{sRegulado}|"
            f"{sCodprov}|{sPrecio1}|{sCantidad}|{sOriginal}|{sDa}|"
            f"{sOferta}|{sUpre}|{sPpre}|{sPsugerido}|{sPgris}|"
            f"{sNuevo}|{sFechafalla}|{sTipocatalogo}|{sCuarentena}|{sDctoneto}|"
            f"{sLote}|{sFecvence}|{sMarcamodelo}|{sPactivo}|{sCosto}|"
            f"{sUbicacion}|{sDescorta}|{sCodisb}|{sFeccatalogo}|{sDepartamento}|"
            f"{sGrupo}|{sSubgrupo}|{sOpc1}|{sOpc2}|{sOpc3}|"
            f"{sPrecio2}|{sPrecio3}|{sPrecio4}|{sPrecio5}|{sVmd}|"
        )
        return linea_completa
