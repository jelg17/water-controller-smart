/* alertas.js — pantalla "Registro de alertas" (US-004, escenario 4).

   Se implementó la consulta de las alertas que Python guardó en la tabla `alertas`:
     - Exceso de tiempo en una actividad (correctiva, solo en la web).
     - Consumo cerca de la meta (preventiva, web + correo).
     - Meta diaria superada (correctiva, web + correo).
   También se muestra si el correo se envió o si falló. */

(function () {
  const contenido = document.getElementById("contenido");

  const TIPOS = {
    exceso_tiempo: "Exceso de tiempo",
    preventiva: "Alerta preventiva",
    exceso_diario: "Meta diaria superada",
  };

  const CORREOS = {
    enviado: '<span class="etiqueta normal">Enviado</span>',
    fallido: '<span class="etiqueta precaucion">No se pudo enviar</span>',
    no_aplica: '<span class="suave">Solo en la web</span>',
  };

  // Los textos se escapan para que nunca se interpreten como HTML
  function escaparHTML(valor) {
    return String(valor).replace(/[&<>"']/g, function (caracter) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[caracter];
    });
  }

  function dibujar(alertas) {
    if (alertas.length === 0) {
      contenido.innerHTML = '<div class="tarjeta vacio">Todavía no se ha generado ninguna alerta.<br>' +
        'Aparecerán aquí cuando una actividad dure demasiado o te acerques a tu meta diaria.</div>';
      return;
    }

    contenido.innerHTML = '<article class="tarjeta"><h3>Alertas generadas</h3>' +
      '<table class="tabla"><thead><tr><th>Fecha</th><th>Hora</th><th>Tipo</th><th>Mensaje</th><th>Correo</th></tr></thead><tbody>' +
      alertas.map(function (a) {
        const clase = a.nivel === "preventiva" ? "precaucion" : "exceso";
        return '<tr><td>' + a.fecha + '</td><td>' + a.hora.slice(0, 5) + '</td>' +
               '<td><span class="etiqueta ' + clase + '">' + escaparHTML(TIPOS[a.tipo] || a.tipo) + '</span></td>' +
               '<td>' + escaparHTML(a.mensaje) + '</td><td>' + (CORREOS[a.correo_estado] || "") + '</td></tr>';
      }).join("") + '</tbody></table></article>';
  }

  fetch("/api/alertas")
    .then(function (respuesta) {
      if (respuesta.status === 401) { window.location = "/"; }
      return respuesta.json();
    })
    .then(function (respuesta) { dibujar(respuesta.alertas || []); })
    .catch(function () {
      contenido.innerHTML = '<div class="alerta">No se pudo conectar con Python. Ejecuta: python app.py</div>';
    });
})();