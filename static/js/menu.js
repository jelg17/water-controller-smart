/* menu.js — dibuja el menú lateral y el encabezado en las páginas internas.
   Cada página dice cuál es en <body data-pagina="..." data-titulo="..." data-subtitulo="...">.
   También manda al login si no hay un usuario guardado.
   Se cambió: ahora el login lo controla Flask (si no hay sesión, ni siquiera entrega la página).
   El correo del usuario llega en <body data-usuario="..."> y las páginas son rutas de Flask. */

(function () {
  const usuario = { correo: document.body.dataset.usuario };

  const cuerpo = document.body;
  // Se quitó "Agregar factura" y se agregó "Alertas" (US-004)
  const paginas = [["panel", "Panel"], ["historial", "Historial"], ["alertas", "Alertas"], ["configuracion", "Configuración"]];
  const gota = '<svg viewBox="0 0 384 512"><path d="M192 0S0 220 0 330c0 100 86 182 192 182s192-82 192-182C384 220 192 0 192 0z"/></svg>';

  const enlaces = paginas.map(function (p) {
    const activo = p[0] === cuerpo.dataset.pagina ? ' class="activo"' : "";
    return '<a href="/' + p[0] + '"' + activo + '>' + p[1] + '</a>';
  }).join("");

  // Armamos: .app > [menú, columna > [encabezado, contenido]]
  const contenido = document.getElementById("contenido");
  const app = document.createElement("div");
  const columna = document.createElement("div");
  app.className = "app";

  app.innerHTML =
    '<nav class="menu">' +
      '<div class="menu-marca"><span class="logo">' + gota + '</span><span>Water Controller<br>Smart</span></div>' +
      enlaces +
      '<div class="menu-usuario"></div>' +
    '</nav>';
  columna.innerHTML =
    '<header class="encabezado"><h1>' + cuerpo.dataset.titulo + '</h1><p class="suave">' + cuerpo.dataset.subtitulo + '</p></header>';

  contenido.before(app);
  columna.append(contenido);
  app.append(columna);

  // Se creó el correo con textContent (nunca se interpreta como HTML) y "Cerrar sesión" va a la ruta /salir de Flask
  const zonaUsuario = app.querySelector(".menu-usuario");
  zonaUsuario.append(document.createTextNode(usuario.correo), document.createElement("br"));
  const salir = document.createElement("a");
  salir.href = "/salir";
  salir.textContent = "Cerrar sesión";
  zonaUsuario.append(salir);
})();