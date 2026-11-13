/* almacen.js — guarda y lee los datos en el localStorage del navegador.

   IMPORTANTE: el localStorage se usa AQUÍ SOLO PARA DEMOSTRACIÓN.
   Guarda los datos en el navegador de cada persona (no se comparten entre
   computadores y se pierden si se borran los datos del sitio). En una versión
   final este archivo se cambiaría por una base de datos real.

   Es el único archivo que usa localStorage; las demás páginas llaman a estas funciones. */

const Almacen = (function () {
  // Nombres con los que se guardan los datos en el navegador
  const CLAVE_FACTURAS = "wcs_facturas";
  const CLAVE_LIMITES = "wcs_limites";
  const CLAVE_USUARIO = "wcs_usuario";

  // Límites con los que empieza el usuario si nunca los ha configurado
  const LIMITES_INICIALES = { mensual: 20, aviso: 80 };   // m3 al mes y % para avisar

  /** Lee un dato; si no existe o está dañado devuelve el valor por defecto. */
  function leer(clave, porDefecto) {
    try {
      const guardado = JSON.parse(localStorage.getItem(clave));
      return guardado === null ? porDefecto : guardado;
    } catch (error) {
      return porDefecto;
    }
  }

  /** localStorage solo guarda texto, por eso el dato se convierte a JSON. */
  function escribir(clave, valor) {
    localStorage.setItem(clave, JSON.stringify(valor));
  }

  // ----- Facturas: { mes: "2026-08", consumo_m3: 14, total: 85430 } -----

  /** Todas las facturas, de la más antigua a la más reciente. */
  function listarFacturas() {
    return leer(CLAVE_FACTURAS, []).sort(function (a, b) { return a.mes.localeCompare(b.mes); });
  }

  function existeFactura(mes) {
    return listarFacturas().some(function (f) { return f.mes === mes; });
  }

  /** Guarda la factura; si ya había una de ese mes, la reemplaza. */
  function guardarFactura(factura) {
    const otras = listarFacturas().filter(function (f) { return f.mes !== factura.mes; });
    otras.push(factura);
    escribir(CLAVE_FACTURAS, otras);
  }

  function borrarFactura(mes) {
    escribir(CLAVE_FACTURAS, listarFacturas().filter(function (f) { return f.mes !== mes; }));
  }

  // ----- Límites -----
  function obtenerLimites() {
    return Object.assign({}, LIMITES_INICIALES, leer(CLAVE_LIMITES, {}));
  }

  function guardarLimites(limites) {
    escribir(CLAVE_LIMITES, limites);
  }

  // ----- Usuario (por ahora solo se guarda el correo con el que entró) -----
  function obtenerUsuario() {
    return leer(CLAVE_USUARIO, null);
  }

  function guardarUsuario(usuario) {
    escribir(CLAVE_USUARIO, usuario);
  }

  function cerrarSesion() {
    localStorage.removeItem(CLAVE_USUARIO);
  }

  return {
    listarFacturas: listarFacturas, existeFactura: existeFactura,
    guardarFactura: guardarFactura, borrarFactura: borrarFactura,
    obtenerLimites: obtenerLimites, guardarLimites: guardarLimites,
    obtenerUsuario: obtenerUsuario, guardarUsuario: guardarUsuario, cerrarSesion: cerrarSesion,
  };
})();
