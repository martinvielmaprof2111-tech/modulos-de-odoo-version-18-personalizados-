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
        if value is None or value == "":
            return "0.00" if decimals == 2 else "0.0000"
        try:
            # Si el valor viene como texto, limpiamos posibles espacios y convertimos comas a puntos
            if isinstance(value, str):
                value = value.replace(',', '.').strip()
            
            float_val = float(value)
            if decimals == 4:
                return f"{float_val:.4f}"
            return f"{float_val:.2f}"
        except (ValueError, TypeError):
            return "0.00" if decimals == 2 else "0.0000"

    def generate_product_line(self, product):
        """
        Mapea y concatena secuencialmente los 41 campos del producto delimitados por '|'.
        Garantiza la extracción de datos maestros del catálogo incluso sin stock disponible.
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
        
        # 7 -> sPrecio1: Precio de venta al público neto (Extraído del maestro del catálogo)
        sPrecio1 = self.format_decimal(product.lst_price)
        
        # 8 -> sCantidad: Stock físico real disponible "A la mano" en Odoo (Permite bajar 0 perfectamente)
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
        
        # 14 -> sPsugerido: Mapeado al precio de venta del catálogo
        sPsugerido = sPrecio1
        
        # 15 -> sPgris: Valor por defecto '0.00'
        sPgris = "0.00"
        
        # 16 -> sNuevo: Valor por defecto '0'
        sNuevo = "0"
        
        # 17 -> sFechafalla: Fecha de última modificación o creación
        sFechafalla = product.write_date.strftime("%Y-%m-%d %H:%M:%S") if product.write_date else fecha_actual
        
        # 18 -> sTipocatalogo: Valor por defecto 'PRINCIPAL'
        sTipocatalogo = "PRINCIPAL"
        
        # 19 -> sCuarentena: Valor por defecto '0'
        sCuarentena = "0"
        
        # 20 -> sDctoneto: Valor por defecto '0.00'
        sDctoneto = "0.00"
        
        # 21 -> sLote: Marcador genérico por defecto
        sLote = "0"
        
        # 22 -> sFecvence: Fecha lejana por defecto si no maneja lotes activos
        sFecvence = "2030-12-31 00:00:00"
        
        # 23 -> sMarcamodelo: Fabricante o proveedor asignado (Búsqueda segura contra nulos)
        sMarcamodelo = "N/A"
        if product.product_tmpl_id.seller_ids and product.product_tmpl_id.seller_ids[0].name:
            sMarcamodelo = self.sanitize_text(product.product_tmpl_id.seller_ids[0].name.name)
        
        # 24 -> sPactivo: Principio activo o descripción de venta
        sPactivo = self.sanitize_text(product.description_sale or "N/A")
        
        # 25 -> sCosto: Costo fijo base de adquisición desde la ficha técnica del producto
        sCosto = self.format_decimal(product.standard_price)
        
        # 26 -> sUbicacion: Ubicación física en anaquel
        sUbicacion = "N/A"
        
        # 27 -> sDescorta: Nombre abreviado a 20 caracteres
        sDescorta = self.sanitize_text(product.name[:20] if product.name else "N/A")
        
        # 28 -> sCodisb: Identificador o RIF de la farmacia desde la configuración
        sCodisb = self.sanitize_text(self.config.cod_isb)
        
        # 29 -> sFeccatalogo: Estampa de tiempo exacta de la extracción
        sFeccatalogo = fecha_actual
        
        # 30 -> sDepartamento: Categoría del producto en Odoo
        sDepartamento = self.sanitize_text(product.categ_id.name)
        
        # 31 -> sGrupo: Clasificación por defecto
        sGrupo = "N/A"
        
        # 32 -> sSubgrupo: Clasificación por defecto
        sSubgrupo = "N/A"
        
        # 33 -> sOpc1: ID de la categoría formateado con ceros a la izquierda
        sOpc1 = str(product.categ_id.id).zfill(5)
        
        # 34 -> sOpc2: Marcador libre
        sOpc2 = "N/A"
        
        # 35 -> sOpc3: Marcador libre
        sOpc3 = "N/A"
        
        # 36 a 39 -> Listas adicionales rellenas en cero
        sPrecio2 = "0.00"
        sPrecio3 = "0.00"
        sPrecio4 = "0.00"
        sPrecio5 = "0.00"
        
        # 40 -> sVmd: Venta Media Diaria estricta con 4 decimales
        sVmd = self.format_decimal(0.0000, decimals=4)

        # --- Ensamble Final de la Fila ---
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