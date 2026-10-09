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
  
/* ----- Caudal de cada actividad (litros por minuto) -----
   Python (servidor.py) valida que sea un número mayor que cero y lo guarda. */
(function () {
  const formulario = document.getElementById("formCaudales");
  const lista = document.getElementById("caudales");
  const mensaje = document.getElementById("mensajeCaudales");
  let catalogo = [];

  function mostrar(texto, esError) {
    mensaje.textContent = texto;
    mensaje.className = "mensaje" + (esError ? " error" : "");
  }

  function cargar() {
    fetch("/api/estado").then(function (r) { return r.json(); }).then(function (estado) {
      catalogo = estado.catalogo;
      lista.innerHTML = catalogo.map(function (a) {
        return '<label class="campo">' + a.nombre + ' (estándar: ' + a.caudal_estandar + ' L/min)' +
               '<input type="text" inputmode="decimal" name="' + a.id + '" value="' + a.caudal + '"></label>';
      }).join("");
    }).catch(function () {
      mostrar("No se pudo conectar con Python. Ejecuta: python servidor.py", true);
    });
  }

  formulario.addEventListener("submit", function (evento) {
    evento.preventDefault();
    // Se envía cada caudal a Python; si alguno no es válido, se muestra su error
    const envios = catalogo.map(function (a) {
      return fetch("/api/caudal", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ actividad: a.id, caudal: formulario.elements[a.id].value }),
      }).then(function (r) { return r.json(); }).then(function (res) {
        return res.ok ? null : a.nombre + ": " + res.error;
      });
    });
    Promise.all(envios).then(function (errores) {
      errores = errores.filter(Boolean);
      if (errores.length) { mostrar(errores.join(" "), true); return; }
      mostrar("Caudales guardados.", false);
      cargar();
    }).catch(function () {
      mostrar("No se pudo conectar con Python. Ejecuta: python servidor.py", true);
    });
  });

  cargar();
})();
})();
