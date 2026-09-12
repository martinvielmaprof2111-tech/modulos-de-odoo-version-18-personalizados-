# -*- coding: utf-8 -*-
from odoo import http
from odoo.http import request
import requests
import hashlib
import logging

_logger = logging.getLogger(__name__)

class PosSitefController(http.Controller):

    @http.route('/pos/sitef/get_token', type='json', auth='public', methods=['POST'], csrf=False)
    def pos_sitef_get_token(self, **kwargs):
        """
        Puente para obtener el Token de SITEF calculando el Content-Length dinámicamente.
        """
        url = "https://api.sitefdevenezuela.com/prod/s4/sitef/apiToken"
        
        headers = {
            "Content-Type": "application/json",
            "Cache-Control": "no-cache"
        }

        username = kwargs.get('username')
        password = kwargs.get('password')

        payload = {
            "username": username,
            "password": password
        }

        try:
            _logger.info("=== SITEF BACKEND: Solicitando Token ===")
            session = requests.Session()
            response = session.post(url, json=payload, headers=headers, timeout=10)
            return response.json()
            
        except Exception as e:
            _logger.error("Error conectando con la API de SITEF para Token: %s", str(e))
            return {"code": 500, "message": "Fallo de conexión con el servidor externo."}

    @http.route('/pos/sitef/send_request', type='json', auth='public', methods=['POST'], csrf=False)
    def pos_sitef_send_request(self, **kwargs):
        """
        Puente transaccional que inyecta el token plano en los Headers 
        y calcula el token MD5 para los parámetros del Body según la documentación.
        """
        endpoint = kwargs.get('endpoint')
        payload = kwargs.get('payload')
        token = kwargs.get('token')

        url = f"https://api.sitefdevenezuela.com/prod/s4/sitefAuth/{endpoint}"
        
        # CORRECCIÓN VITAL: El switch de SITEF requiere el prefijo 'Bearer ' dentro de la cadena a hashear en MD5
        token_limpio = str(token).strip()
        if not token_limpio.startswith("Bearer "):
            bearer_completo = f"Bearer {token_limpio}"
        else:
            bearer_completo = token_limpio

        # Generación del Hash MD5 exacto en una sola línea continua libre de saltos de línea
        token_md5_hash = hashlib.md5(bearer_completo.encode('utf-8')).hexdigest()

        if isinstance(payload, dict):
            # Inyectamos la firma corregida exigida por la pasarela
            payload['token'] = token_md5_hash
            
            # Normalización adaptativa de campos antiguos de vuelto/transferencia
            if 'destinationmobilenumber' not in payload and 'destinationmobilnumber' in payload:
                payload['destinationmobilenumber'] = payload.pop('destinationmobilnumber')

            # --- CORRECCIÓN DE TIPADO PARA EVITAR EXCEPCIONES EN EL ENDPOINT JAVA ---
            # Si el payload contiene idBranch o enteros como bancos, nos aseguramos que viajen como tipo numérico
            if 'idBranch' in payload and payload['idBranch']:
                payload['idBranch'] = int(payload['idBranch'])
            if 'idbranch' in payload and payload['idbranch']:
                payload['idbranch'] = int(payload['idbranch'])
                
            if 'origenbank' in payload and payload['origenbank']:
                payload['origenbank'] = int(payload['origenbank'])
            if 'receivingBank' in payload and payload['receivingBank']:
                payload['receivingBank'] = int(payload['receivingBank'])
            if 'receivingBank' not in payload and 'receivingbank' in payload:
                payload['receivingBank'] = int(payload.pop('receivingbank'))

        # Armamos los Headers puros de la petición HTTP
        headers = {
            "Content-Type": "application/json",
            "Authorization": bearer_completo,
            "Cache-Control": "no-cache"
        }

        try:
            _logger.info("=== SITEF BACKEND: Enviando operación transaccional a: %s ===", endpoint)
            _logger.info("=== SITEF BACKEND: Payload a transmitir: %s ===", payload)
            
            session = requests.Session()
            response = session.post(url, json=payload, headers=headers, timeout=15)
            
            _logger.info("=== SITEF BACKEND: Código de respuesta transaccional: %s ===", response.status_code)
            _logger.info("=== SITEF BACKEND: Respuesta transaccional Raw: %s ===", response.text)
            return response.json()
            
        except Exception as e:
            _logger.error("Error en petición transaccional SITEF (%s): %s", endpoint, str(e))
            return {"status": "error", "message": "Fallo de comunicación en el puente del servidor Odoo."}