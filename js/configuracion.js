/* configuracion.js — límite mensual de consumo y porcentaje a partir del cual se avisa. */

(function () {
  const formulario = document.getElementById("formulario");
  const mensaje = document.getElementById("mensaje");

  // Mostramos los valores guardados
  const limites = Almacen.obtenerLimites();
  formulario.mensual.value = limites.mensual;
  formulario.aviso.value = limites.aviso;

  formulario.addEventListener("submit", function (evento) {
    evento.preventDefault();
    const mensual = parseFloat(formulario.mensual.value);
    const aviso = parseInt(formulario.aviso.value, 10);

    // Validamos antes de guardar
    if (!(mensual > 0) || !(aviso >= 1 && aviso <= 100)) {
      mensaje.textContent = "El límite debe ser mayor que cero y el porcentaje estar entre 1 y 100.";
      return;
    }
    Almacen.guardarLimites({ mensual: mensual, aviso: aviso });
    mensaje.textContent = "Límites guardados.";
  });
})();
