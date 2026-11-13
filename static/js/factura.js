/* factura.js — pantalla "Agregar factura".

   Cómo funciona:
     1. El usuario llena el formulario.
     2. Se lo mandamos a Python (servidor.py), que REVISA los datos.
     3. Si Python dice que están bien, la factura se guarda en el localStorage. */

(function () {
  const formulario = document.getElementById("formulario");
  const mensaje = document.getElementById("mensaje");
  const lista = document.getElementById("lista");

  function mostrarMensaje(texto, esError) {
    mensaje.textContent = texto;
    mensaje.className = "mensaje" + (esError ? " error" : "");
  }

  /** Dibuja la tabla con las facturas guardadas (la más reciente primero). */
  function mostrarLista() {
    const facturas = Almacen.listarFacturas().reverse();
    if (facturas.length === 0) {
      lista.innerHTML = '<tr><td colspan="4" class="suave">Aún no hay facturas guardadas.</td></tr>';
      return;
    }
    lista.innerHTML = facturas.map(function (f) {
      return '<tr><td>' + Calculos.nombreMes(f.mes) + '</td><td>' + f.consumo_m3 + ' m³</td>' +
             '<td>' + Calculos.pesos(f.total) + '</td>' +
             '<td><button class="borrar" data-mes="' + f.mes + '">Borrar</button></td></tr>';
    }).join("");
  }

  formulario.addEventListener("submit", function (evento) {
    evento.preventDefault();   // evita que el navegador recargue la página

    const datos = {
      mes: formulario.mes.value,
      consumo: formulario.consumo.value,
      total: formulario.total.value,
    };

    // Le enviamos los datos a Python para que los revise
    fetch("/api/factura", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(datos),
    })
      .then(function (respuesta) { return respuesta.json(); })
      .then(function (resultado) {
        if (!resultado.ok) {
          mostrarMensaje(resultado.error, true);   // Python encontró un problema
          return;
        }
        // Si ya había una factura de ese mes, preguntamos antes de reemplazarla
        if (Almacen.existeFactura(resultado.factura.mes) &&
            !confirm("Ya hay una factura de ese mes. ¿Quieres reemplazarla?")) {
          return;
        }
        Almacen.guardarFactura(resultado.factura);
        formulario.reset();
        mostrarMensaje("Factura guardada.", false);
        mostrarLista();
      })
      .catch(function () {
        mostrarMensaje("No se pudo conectar con Python. Ejecuta: python servidor.py", true);
      });
  });

  // Botones "Borrar" de la tabla (un solo escuchador para todos)
  lista.addEventListener("click", function (evento) {
    const mes = evento.target.dataset.mes;
    if (mes) {
      Almacen.borrarFactura(mes);
      mostrarLista();
    }
  });

  mostrarLista();
})();
