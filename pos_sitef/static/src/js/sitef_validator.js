/** @odoo-module **/

export const ValidadorSitef = {
    transaccionEnCurso: false,
    referenciasProcesadas: new Set(),

    validarFlujoPago(wizardActual, textoMetodo) {
        if (this.transaccionEnCurso) {
            return {
                esValido: false,
                mensaje: "Espere un momento. Existe una consulta a la pasarela SITEF actualmente en progreso."
            };
        }
        return { esValido: true, mensaje: "" };
    },

    validarPaso(paso, datos) {
        if (!datos) {
            return { esValido: false, mensaje: "Error crítico: Los datos del asistente no se inicializaron." };
        }

        if (paso === 1) {
            const cedula = (datos.cedula_numero || "").trim();
            if (!cedula) {
                return { esValido: false, mensaje: "Debe ingresar el número de cédula o RIF del cliente." };
            }
            if (cedula.length < 6) {
                return { esValido: false, mensaje: "El número de cédula o RIF ingresado es demasiado corto (Mínimo 6 dígitos)." };
            }
            if (!/^\d+$/.test(cedula)) {
                return { esValido: false, mensaje: "La cédula o RIF solo debe contener números en este campo." };
            }
        } 
        
        else if (paso === 2) {
            const telefono = (datos.telefono || "").trim();
            const banco = (datos.banco_id || "").trim();

            if (!telefono) {
                return { esValido: false, mensaje: "Debe ingresar el número de teléfono celular asociado al Pago Móvil." };
            }
            if (telefono.length !== 11) {
                return { esValido: false, mensaje: "El número de teléfono debe tener exactamente 11 dígitos (Ejemplo: 04121234567)." };
            }
            if (!telefono.startsWith("04")) {
                return { esValido: false, mensaje: "El número de teléfono celular debe iniciar con un prefijo válido (0412, 0414, 0424, 0416, 0426)." };
            }
            if (!banco) {
                return { esValido: false, mensaje: "Debe seleccionar el banco emisor de origen desde la lista desplegable." };
            }
        } 
        
        else if (paso === 3) {
            const montoOperacion = parseFloat(datos.amountBs || 0);

            if (datos.esVuelto) {
                if (isNaN(montoOperacion) || montoOperacion <= 0) {
                    return { esValido: false, mensaje: "Debe ingresar un monto de vuelto válido y mayor a cero." };
                }
                return { esValido: true, mensaje: "" };
            }

            if (isNaN(montoOperacion) || montoOperacion <= 0) {
                return { esValido: false, mensaje: "El monto total de la operación debe ser un número válido mayor a cero." };
            }

            const referencia = (datos.referencia || "").trim();
            if (!referencia) {
                return { esValido: false, mensaje: "Debe introducir el número de referencia del Pago Móvil recibido." };
            }
            
            if (referencia.length < 6 || referencia.length > 8) {
                return { esValido: false, mensaje: "La referencia introducida no posee una longitud válida (Debe tener entre 6 y 8 dígitos)." };
            }
            if (!/^\d+$/.test(referencia)) {
                return { esValido: false, mensaje: "El número de referencia debe contener únicamente caracteres numéricos." };
            }
        }

        return { esValido: true, mensaje: "" };
    },

    validarConectividad() {
        if (navigator && typeof navigator.onLine !== "undefined" && !navigator.onLine) {
            return {
                esValido: false,
                mensaje: "Sin conexión: Detectamos que esta caja no posee salida a internet. Compruebe su red antes de verificar el pago."
            };
        }
        return { esValido: true, mensaje: "" };
    },

    validarReferenciaUnica(referencia) {
        const refLimpia = referencia.trim();
        if (this.referenciasProcesadas.has(refLimpia)) {
            return {
                esValido: false,
                mensaje: `Alerta Antifraude: La referencia bancaria [${refLimpia}] ya fue validada y procesada con éxito en un pedido anterior de esta sesión.`
            };
        }
        return { esValido: true, mensaje: "" };
    },

    registrarReferencia(referencia) {
        if (referencia) {
            this.referenciasProcesadas.add(referencia.trim());
        }
    },

    limpiarEstado() {
        this.transaccionEnCurso = false;
        if (window.currentSitefWizard) {
            window.currentSitefWizard.step = 1;
        }
    }
};