/* calculos.js — cuentas sencillas con el consumo. No toca la pantalla ni el localStorage. */

const Calculos = {
  /** Compara el consumo con el límite y dice si va Normal, en Precaución o en Exceso. */
  estado: function (consumo, limites) {
    const porcentaje = consumo / limites.mensual * 100;
    if (porcentaje >= 100) return { porcentaje: porcentaje, nombre: "Exceso", clase: "exceso" };
    if (porcentaje >= limites.aviso) return { porcentaje: porcentaje, nombre: "Precaución", clase: "precaucion" };
    return { porcentaje: porcentaje, nombre: "Normal", clase: "normal" };
  },

  /** Promedio del consumo de todas las facturas. */
  promedio: function (facturas) {
    const suma = facturas.reduce(function (total, f) { return total + f.consumo_m3; }, 0);
    return suma / facturas.length;
  },

  /** 2026-08 -> "agosto 2026" */
  nombreMes: function (mes) {
    const nombres = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio",
                     "agosto", "septiembre", "octubre", "noviembre", "diciembre"];
    const partes = mes.split("-");
    return nombres[Number(partes[1]) - 1] + " " + partes[0];
  },

  /** 85400 -> "$85.400" */
  pesos: function (valor) {
    return "$" + Math.round(valor).toLocaleString("es-CO");
  },
};
