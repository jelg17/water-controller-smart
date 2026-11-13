/* panel.js — pantalla principal.

   Arriba: registro de actividades (US-001) y consumo del día (US-002).
     - Cronómetro de acceso rápido: un clic inicia y otro clic detiene.
     - Registro manual: actividad + minutos.
     - Python (app.py) valida, calcula los litros y guarda; aquí solo se muestra.
   Se quitó el resumen de facturas de siempre (ya no se suben facturas).
   Se implementó US-003 y US-004: el estado del día (Normal / Precaución / Exceso) y las
   alertas que Python genera al registrar una actividad se muestran como avisos en pantalla. */

(function () {
  const contenido = document.getElementById("contenido");
  let estado = null;        // lo último que respondió Python (/api/estado)
  let reloj = null;         // temporizador que mueve el cronómetro en pantalla

  // ---------- Comunicación con Python ----------
  function pedir(ruta, datos) {
    const opciones = datos === undefined ? {} : {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(datos),
    };
    return fetch(ruta, opciones).then(function (respuesta) {
      // Se agregó: si la sesión expiró, Flask responde 401 y se vuelve al login
      if (respuesta.status === 401) { window.location = "/"; }
      return respuesta.json();
    });
  }

  function sinConexion() {
    mostrarResultado("No se pudo conectar con Python. Ejecuta: python app.py", "error");
  }

  // ---------- Armado de la pantalla (una sola vez) ----------
  contenido.innerHTML =
    '<div id="resultado"></div>' +
    '<section class="grid2">' +
      '<article class="tarjeta"><h3>Cronómetro rápido</h3>' +
        '<p class="suave">Elige una actividad para iniciar. Vuelve a presionar para detenerla.</p>' +
        '<div id="cronometro"></div></article>' +
      '<form class="tarjeta formulario" id="manual"><h3>Registrar con minutos</h3>' +
        '<label class="campo">Actividad<select name="actividad" id="selector"></select></label>' +
        '<label class="campo">Duración (minutos)' +
          '<input type="text" inputmode="decimal" name="minutos" placeholder="Ej: 7,5"></label>' +
        '<p class="mensaje" id="mensaje"></p>' +
        '<div><button class="boton">Guardar actividad</button></div></form>' +
    '</section>' +
    '<section class="grid3" id="resumen"></section>' +
    '<section class="grid2" id="logros"></section>' +
    '<article class="tarjeta" id="semana"></article>' +
    '<article class="tarjeta"><h3>Actividades de hoy</h3><div id="tabla"></div></article>';

  const zonaResultado = document.getElementById("resultado");
  const zonaCronometro = document.getElementById("cronometro");
  const formulario = document.getElementById("manual");
  const mensaje = document.getElementById("mensaje");

  function mostrarResultado(texto, tipo) {
    zonaResultado.innerHTML = "";
    if (!texto) return;
    const aviso = document.createElement("div");
    aviso.className = "alerta" + (tipo === "ok" ? " ok" : "");
    aviso.textContent = texto;            // textContent: el texto nunca se interpreta como HTML
    zonaResultado.append(aviso);
  }

  /** US-004: dibuja debajo del resultado las alertas que generó Python al registrar. */
  function mostrarAlertas(alertas) {
    (alertas || []).forEach(function (alerta) {
      const aviso = document.createElement("div");
      aviso.className = "alerta" + (alerta.nivel === "preventiva" ? " aviso" : "");
      aviso.textContent = alerta.mensaje;
      zonaResultado.append(aviso);

      // Escenario 3: si el correo falló, el aviso queda visible en el banner de la aplicación
      if (alerta.correo_estado === "fallido") {
        const fallo = document.createElement("div");
        fallo.className = "alerta aviso";
        fallo.textContent = "No se pudo enviar el correo de esta alerta (" + alerta.correo_error + ") " +
                            "Te la mostramos aquí y quedó guardada en tu registro de alertas.";
        zonaResultado.append(fallo);
      } else if (alerta.correo_estado === "enviado") {
        const enviado = document.createElement("div");
        enviado.className = "alerta ok";
        enviado.textContent = "También te enviamos esta alerta por correo electrónico.";
        zonaResultado.append(enviado);
      }
    });
  }

  // ---------- Dibujo de cada parte ----------
  function formatoReloj(segundos) {
    const s = Math.floor(segundos);
    const dos = function (n) { return String(n).padStart(2, "0"); };
    return dos(Math.floor(s / 3600)) + ":" + dos(Math.floor(s / 60) % 60) + ":" + dos(s % 60);
  }

  function coma(numero) {          // 7.5 -> "7,5"
    return String(numero).replace(".", ",");
  }

  function litros(valor) {
    return valor.toLocaleString("es-CO", { minimumFractionDigits: 1, maximumFractionDigits: 1 }) + " L";
  }

  function dibujarCronometro() {
    clearInterval(reloj);
    if (estado.cronometro) {
      const base = estado.cronometro.segundos, desde = performance.now();
      zonaCronometro.innerHTML =
        '<p class="suave">En marcha: <strong>' + estado.cronometro.nombre + '</strong></p>' +
        '<strong class="dato reloj" id="reloj">' + formatoReloj(base) + '</strong>' +
        '<button class="boton detener" data-detener="1">Detener y guardar</button>';
      reloj = setInterval(function () {
        document.getElementById("reloj").textContent = formatoReloj(base + (performance.now() - desde) / 1000);
      }, 250);
      return;
    }
    zonaCronometro.innerHTML = '<div class="acciones">' + estado.catalogo.map(function (a) {
      return '<button class="boton" data-actividad="' + a.id + '">▶ ' + a.nombre + '</button>';
    }).join("") + '</div>';
  }

  function dibujarSelector() {
    const selector = document.getElementById("selector");
    if (selector.options.length) return;   // ya estaba lleno
    selector.innerHTML = estado.catalogo.map(function (a) {
      return '<option value="' + a.id + '">' + a.nombre + ' (' + coma(a.caudal) + ' L/min)</option>';
    }).join("");
  }

  function dibujarResumen() {
    const hoy = estado.hoy;
    const ultima = hoy.actividades[hoy.actividades.length - 1];
    const meta = estado.meta_diaria;
    const porcentaje = hoy.porcentaje_meta;
    let aviso = "";

    // US-003: el estado del día lo calcula Python (Normal / Precaución / Exceso)
    if (hoy.estado === "exceso") {
      aviso = '<div class="alerta">Exceso: superaste tu meta diaria.</div>';
    } else if (hoy.estado === "precaucion") {
      aviso = '<div class="alerta aviso">Precaución: estás cerca de tu meta diaria.</div>';
    } else {
      aviso = '<div class="alerta ok">Normal: vas dentro de tu meta diaria.</div>';
    }

    document.getElementById("resumen").innerHTML =
      '<article class="tarjeta"><span class="suave">Consumo de hoy</span>' +
        '<strong class="dato">' + litros(hoy.total_litros) + '</strong>' +
        '<p class="suave">Consumo acumulado del dia</p></article>' +

      '<article class="tarjeta"><span class="suave">Actividades de hoy</span>' +
        '<strong class="dato">' + hoy.cantidad + '</strong>' +
        '<p class="suave">Actividades registradas</p></article>' +

      '<article class="tarjeta"><span class="suave">Ultima actividad</span>' +
        '<strong class="dato">' + (ultima ? ultima.nombre : "Sin registros") + '</strong>' +
        '<p class="suave">' +
          (ultima ? litros(ultima.litros) + " - " + ultima.hora.slice(0, 5) : "Aun no hay registros") +
        '</p></article>' +

      '<article class="tarjeta"><span class="suave">Meta diaria</span>' +
        '<strong class="dato">' + litros(meta) + '</strong>' +
        '<p class="suave">Consumo: ' + litros(hoy.total_litros) + '</p>' +
        '<p class="suave">Cumplimiento: ' + porcentaje + '%</p>' +
        '<p class="suave">Estado: <strong class="color-' + hoy.estado + '">' + hoy.estado_nombre + '</strong></p>' +
        '<progress max="100" value="' + Math.min(porcentaje, 100) +
          '" style="width:100%"></progress>' +
        aviso +
      '</article>';
  }

  function dibujarTabla() {
    const actividades = estado.hoy.actividades.slice().reverse();   // la más reciente primero
    if (actividades.length === 0) {
      document.getElementById("tabla").innerHTML =
        '<p class="suave">Aún no registras actividades hoy. Usa el cronómetro o escribe los minutos.</p>';
      return;
    }
    document.getElementById("tabla").innerHTML =
      '<table class="tabla"><thead><tr><th>Hora</th><th>Actividad</th><th>Duración</th><th>Caudal</th>' +
      '<th>Litros</th><th>Podrías ahorrar</th><th>Estado</th></tr></thead><tbody>' +
      actividades.map(function (a) {
        return '<tr><td>' + a.hora.slice(0, 5) + '</td><td>' + a.nombre + '</td><td>' + coma(a.minutos) + ' min</td>' +
               '<td>' + coma(a.caudal) + ' L/min' + (a.caudal_personalizado ? ' ✎' : '') + '</td>' +
               '<td>' + litros(a.litros) + '</td><td>' + (a.ahorro_litros > 0 ? litros(a.ahorro_litros) : "—") + '</td>' +
               // US-003: se marca la actividad que superó el tiempo recomendado
               '<td>' + (a.exceso_tiempo ? '<span class="etiqueta exceso">Exceso de tiempo</span>' : '<span class="etiqueta normal">Normal</span>') + '</td></tr>';
      }).join("") + '</tbody></table>';
  }
  
  /** Racha, insignias y consejos de ahorro: los calcula Python (logros.py) y llegan por /api/logros. */
  function dibujarLogros(datos) {
    document.getElementById("logros").innerHTML =
      '<article class="tarjeta"><h3>Racha y logros</h3>' +
        '<div class="racha">' +
          '<div><strong class="dato" id="rachaActual"></strong><span class="suave">días seguidos dentro de tu meta</span></div>' +
          '<div><strong class="dato" id="mejorRacha"></strong><span class="suave">mejor racha</span></div>' +
        '</div>' +
        '<div class="insignias" id="insignias"></div></article>' +
      '<article class="tarjeta"><h3>Consejos para ti</h3><ul class="consejos" id="consejos"></ul></article>';

    document.getElementById("rachaActual").textContent = "🔥 " + datos.racha_actual;
    document.getElementById("mejorRacha").textContent = "🏆 " + datos.mejor_racha;

    // textContent en todo: los nombres nunca se interpretan como HTML
    datos.insignias.forEach(function (i) {
      const caja = document.createElement("div");
      const icono = document.createElement("span");
      const nombre = document.createElement("strong");
      const progreso = document.createElement("span");
      caja.className = "insignia" + (i.obtenida ? "" : " bloqueada");
      caja.title = i.descripcion;
      icono.className = "icono";
      icono.textContent = i.icono;
      nombre.textContent = i.nombre;
      progreso.className = "suave";
      progreso.textContent = i.obtenida ? "¡Lograda!" : i.progreso + " / " + i.objetivo;
      caja.append(icono, nombre, document.createElement("br"), progreso);
      document.getElementById("insignias").append(caja);
    });

    datos.consejos.forEach(function (c) {
      const item = document.createElement("li");
      item.textContent = c.icono + " " + c.texto;
      document.getElementById("consejos").append(item);
    });
  }

  function cargarLogros() {
    pedir("/api/logros").then(function (respuesta) {
      if (respuesta.ok) dibujarLogros(respuesta);
    }).catch(function () { /* si falla, el resto del panel sigue funcionando */ });
  }

  /** Resumen de los últimos 7 días (lo calcula Python en /api/resumen-semanal) y botón para recibirlo por correo. */
  function dibujarSemana(r) {
    const zona = document.getElementById("semana");

    if (r.sin_datos) {
      zona.innerHTML = '<h3>Tu semana</h3><p class="suave">Aún no hay actividades en los últimos 7 días.</p>';
      return;
    }

    zona.innerHTML =
      '<h3>Tu semana</h3>' +
      '<p class="suave" id="semRango"></p>' +
      '<div class="racha">' +
        '<div><strong class="dato" id="semTotal"></strong><span class="suave" id="semVar"></span></div>' +
        '<div><strong class="dato" id="semProm"></strong><span class="suave">promedio diario</span></div>' +
        '<div><strong class="dato" id="semDias"></strong><span class="suave">días dentro de tu meta</span></div>' +
      '</div>' +
      '<p class="suave" id="semMejor"></p>' +
      '<div class="acciones"><button class="boton" id="enviarResumen">✉️ Enviarme el resumen por correo</button></div>' +
      '<p class="mensaje" id="resumenMsg"></p>';

    document.getElementById("semRango").textContent = r.desde + " al " + r.hasta;
    document.getElementById("semTotal").textContent = litros(r.total_litros);
    document.getElementById("semVar").textContent = r.variacion === null
      ? "sin semana anterior para comparar"
      : (r.variacion > 0 ? "▲ +" : "▼ ") + coma(r.variacion) + "% vs semana anterior";
    document.getElementById("semProm").textContent = litros(r.promedio_diario);
    document.getElementById("semDias").textContent = r.dias_en_meta + " de " + r.dias_con_registros;
    document.getElementById("semMejor").textContent = r.mejor_dia
      ? "Mejor día: " + r.mejor_dia.etiqueta + " (" + litros(r.mejor_dia.litros) + ")" +
        (r.actividad_top ? " · Lo que más agua usó: " + r.actividad_top.nombre + " (" + r.actividad_top.porcentaje + "%)" : "")
      : "";

    const boton = document.getElementById("enviarResumen");
    const msg = document.getElementById("resumenMsg");
    boton.addEventListener("click", function () {
      boton.disabled = true;
      msg.className = "mensaje";
      msg.textContent = "Enviando...";
      pedir("/api/resumen-semanal/enviar", {}).then(function (res) {
        msg.textContent = res.ok ? "Listo: te enviamos el resumen a tu correo." : res.error;
        msg.className = "mensaje" + (res.ok ? "" : " error");
      }).catch(function () {
        msg.textContent = "No se pudo conectar con Python.";
        msg.className = "mensaje error";
      }).then(function () { boton.disabled = false; });
    });
  }

  function cargarSemana() {
    pedir("/api/resumen-semanal").then(function (respuesta) {
      if (respuesta.ok) dibujarSemana(respuesta);
    }).catch(function () { /* si falla, el resto del panel sigue funcionando */ });
  }

  function dibujarTodo() {
    dibujarSelector();
    dibujarCronometro();
    dibujarResumen();
    dibujarTabla();
  }

  function cargarEstado() {
    return pedir("/api/estado").then(function (respuesta) {
      estado = respuesta;
      dibujarTodo();
      cargarLogros();
      cargarSemana();   // se agregó: resumen de la semana
    }).catch(sinConexion);
  }

  /** Muestra lo que respondió Python al registrar (error o mensaje con los litros). */
  function mostrarRespuestaRegistro(respuesta) {
    if (!respuesta.ok) {
      mostrarResultado(respuesta.error, "error");
      return;
    }
    mostrarResultado(respuesta.registro.mensaje + " Consumo de hoy: " + litros(respuesta.hoy.total_litros) + ".", "ok");
    mostrarAlertas(respuesta.alertas);
  }

  // ---------- Eventos ----------
  // Cronómetro: un solo escuchador para todos los botones
  zonaCronometro.addEventListener("click", function (evento) {
    const boton = evento.target.closest("button");
    if (!boton) return;

    if (boton.dataset.actividad) {                          // iniciar
      pedir("/api/cronometro/iniciar", { actividad: boton.dataset.actividad }).then(function (respuesta) {
        mostrarResultado(respuesta.ok ? "" : respuesta.error, "error");
        return cargarEstado();
      }).catch(sinConexion);
    } else if (boton.dataset.detener) {                     // detener y guardar
      pedir("/api/cronometro/detener", {}).then(function (respuesta) {
        mostrarRespuestaRegistro(respuesta);
        return cargarEstado();
      }).catch(sinConexion);
    }
  });

  // Registro manual
  formulario.addEventListener("submit", function (evento) {
    evento.preventDefault();
    pedir("/api/actividad", {
      actividad: formulario.actividad.value,
      minutos: formulario.minutos.value,
    }).then(function (respuesta) {
      if (respuesta.ok) {
        formulario.minutos.value = "";
        mensaje.textContent = "";
        mensaje.className = "mensaje";
        mostrarRespuestaRegistro(respuesta);
        return cargarEstado();
      }
      mensaje.textContent = respuesta.error;               // el error aparece junto al campo
      mensaje.className = "mensaje error";
    }).catch(sinConexion);
  });

  cargarEstado();
})();