# -*- coding: utf-8 -*-

import logging
import werkzeug.wrappers
from odoo import http
from odoo.http import request
from ..utils.icompras_utils_exportador import IcomprasDataExporter

_logger = logging.getLogger(__name__)

class IcomprasApiController(http.Controller):

    @http.route('/api/v1/icompras/inventario', type='http', auth='none', methods=['GET'], csrf=False)
    def get_icompras_inventario(self, **kwargs):
        """
        Endpoint REST que expone la traza del inventario en formato de texto plano.
        Filtra de forma estricta por farmacia (compañía) evaluando el Token Bearer.
        """
        # 1. Extraer la cabecera de autenticación
        auth_header = request.httprequest.headers.get('Authorization')
        if not auth_header or not auth_header.startswith('Bearer '):
            _logger.warning("[iCompras360 API] Intento de acceso rechazado: Cabecera Authorization ausente o mal estructurada.")
            return werkzeug.wrappers.Response("No autorizado: Falta el token de seguridad.", status=401)

        # Extraer el token crudo enviado por el cliente
        token_recibido = auth_header.split(" ")[1].strip()

        # 2. Inicializar el entorno interno (request.env) usando el superusuario raíz
        uid = request.env.ref('base.user_root').id
        env = request.env(user=uid)

        # 3. ADAPTACIÓN MULTIFARMACIA: Buscar la configuración comparando el Token recibido directamente
        config = env['icompras.config'].search([
            ('api_token', '=', token_recibido),
            ('active', '=', True)
        ], limit=1)

        if not config:
            _logger.warning("[iCompras360 API] Intento de acceso fallido: El token proporcionado no coincide con ninguna farmacia activa.")
            return werkzeug.wrappers.Response("No autorizado: Token de seguridad inválido.", status=401)

        # Obtener la compañía asociada a esta configuración específica de farmacia
        company_id = getattr(config, 'company_id', env.company)

        _logger.info(f"[iCompras360 API] Conexión autorizada para la farmacia con Código ISB {config.cod_isb} (Compañía: {company_id.name}). Generando traza...")

        # 4. FILTRO DE PRODUCTOS MODIFICADO: Volvemos a la búsqueda global exitosa del código anterior 
        # pero añadiendo el contexto de la compañía para que jale la información correspondiente sin trabarse.
        products = env['product.product'].with_company(company_id).search([
            ('active', '=', True),
            ('sale_ok', '=', True)
        ])

        if not products:
            _logger.info(f"[iCompras360 API] Proceso terminado. El inventario para la farmacia {config.cod_isb} está vacío.")
            return request.make_response("", headers=[('Content-Type', 'text/plain; charset=utf-8')])

        # 5. Invocar al motor de la Fase 2 para procesar el catálogo
        exporter = IcomprasDataExporter(env, config)
        lineas_archivo = []

        for product in products:
            try:
                linea = exporter.generate_product_line(product)
                
                if linea:
                    # REVISIÓN DE DELIMITADOR: Conservamos rigurosamente el pipeline final exigido por el TXT
                    if not linea.endswith('|'):
                        linea = f"{linea}|"
                    lineas_archivo.append(linea)
                    
            except Exception as e:
                _logger.error(f"[iCompras360 API] Error omitiendo producto ID {product.id} para farmacia {config.cod_isb}: {str(e)}")

        # Unimos todas las líneas usando el salto de línea para Windows (\r\n)
        contenido_completo = "\r\n".join(lineas_archivo) + "\r\n"

        _logger.info(f"[iCompras360 API] Traza multifarmacia generada con éxito. Total registros enviados: {len(lineas_archivo)} para ISB {config.cod_isb}.")

        # 6. Retornar la respuesta de texto plano crudo
        headers = [
            ('Content-Type', 'text/plain; charset=utf-8'),
            ('Content-Length', str(len(contenido_completo.encode('utf-8'))))
        ]
        return request.make_response(contenido_completo, headers=headers)