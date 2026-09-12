/** @odoo-module **/
import { rpc } from "@web/core/network/rpc";
import { SitefAuthService } from "@pos_sitef_pay/js/sitef_auth_service";

export const SitefService = {
    /**
     * Despacha una petición transaccional hacia el Switch de SITEF a través de Odoo.
     * @param {string} endpoint - Acción destino (getBusquedaSitef o setVueltoSitef)
     * @param {Object} payload - Datos de la operación armada por la interfaz
     * @returns {Promise<Object>} Resultado con estatus de la operación
     */
    async ejecutarOperacion(endpoint, payload) {
        const token = await SitefAuthService.getToken();
        if (!token) {
            return { success: false, message: "Error de autenticación: No se pudo generar un token de acceso seguro." };
        }

        try {
            const response = await rpc("/pos/sitef/send_request", {
                endpoint: endpoint,
                payload: payload,
                token: token
            });
            return { success: true, data: response };
        } catch (error) {
            console.error("Fallo de comunicación en la red transaccional RPC:", error);
            return { success: false, message: error.message };
        }
    },

    /**
     * Muestra un banner temporal en la UI del Punto de Venta con el estatus del proceso.
     * @param {string|number} monto - Monto de la operación
     * @param {string} mensaje - Texto descriptivo
     */
    desplegarBannerNotificacion(monto, mensaje) {
        const bannerPrevio = document.querySelector(".sitef-ui-banner-info");
        if (bannerPrevio) bannerPrevio.remove();

        const banner = document.createElement("div");
        banner.className = "sitef-ui-banner-info";
        
        const montoNumerico = typeof monto === 'number' ? monto : parseFloat(monto || 0);
        const montoFormateado = isNaN(montoNumerico) ? "0.00" : montoNumerico.toFixed(2);

        banner.innerHTML = `<span><strong>[SITEF]:</strong> ${mensaje} - Monto: <strong>${montoFormateado} Bs.</strong></span>`;
        document.body.appendChild(banner);
        
        setTimeout(() => { 
            if (banner.parentNode) {
                banner.remove(); 
            }
        }, 4000);
    }
};