/** @odoo-module **/
import { rpc } from "@web/core/network/rpc";

export const SitefAuthService = {
    /**
     * Solicita el token de autenticación al backend de Odoo.
     * El controlador de Python se encarga de inyectar las credenciales configuradas en el sistema.
     * @returns {Promise<string|null>} Token válido o null en caso de fallo
     */
    async getToken() {
        try {
            const response = await rpc("/pos/sitef/get_token");
            
            if (response && response.data && response.data.token) {
                return response.data.token;
            }
            return response?.token || null; 
        } catch (error) {
            console.error("Error crítico obteniendo token de autenticación:", error);
            return null;
        }
    }
};