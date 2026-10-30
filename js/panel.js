/* panel.js — pantalla principal.

   Arriba: registro de actividades (US-001) y consumo del día (US-002).
     - Cronómetro de acceso rápido: un clic inicia y otro clic detiene.
     - Registro manual: actividad + minutos.
     - Python (servidor.py) valida, calcula los litros y guarda; aquí solo se muestra.
   Abajo: el resumen de facturas de siempre. */

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
    return fetch(ruta, opciones).then(function (respuesta) { return respuesta.json(); });
  }

  function sinConexion() {
    mostrarResultado("No se pudo conectar con Python. Ejecuta: python servidor.py", "error");
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

    if (hoy.meta_superada) {
      aviso = '<div class="alerta">Has alcanzado o superado tu meta diaria.</div>';
    } else if (hoy.meta_cercana) {
      aviso = '<div class="alerta aviso">Atencion: estas cerca de tu meta diaria.</div>';
    } else {
      aviso = '<div class="alerta ok">Vas dentro de tu meta diaria.</div>';
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
      '<th>Litros</th><th>Podrías ahorrar</th></tr></thead><tbody>' +
      actividades.map(function (a) {
        return '<tr><td>' + a.hora.slice(0, 5) + '</td><td>' + a.nombre + '</td><td>' + coma(a.minutos) + ' min</td>' +
               '<td>' + coma(a.caudal) + ' L/min' + (a.caudal_personalizado ? ' ✎' : '') + '</td>' +
               '<td>' + litros(a.litros) + '</td><td>' + (a.ahorro_litros > 0 ? litros(a.ahorro_litros) : "—") + '</td></tr>';
      }).join("") + '</tbody></table>';
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
    }).catch(sinConexion);
  }

  /** Muestra lo que respondió Python al registrar (error o mensaje con los litros). */
  function mostrarRespuestaRegistro(respuesta) {
    if (!respuesta.ok) {
      mostrarResultado(respuesta.error, "error");
      return;
    }
    mostrarResultado(respuesta.registro.mensaje + " Consumo de hoy: " + litros(respuesta.hoy.total_litros) + ".", "ok");
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

  // ---------- Facturas (lo que ya existía) ----------
  function dibujarFacturas() {
    const facturas = Almacen.listarFacturas();
    const limites = Almacen.obtenerLimites();

    if (facturas.length === 0) {
      contenido.insertAdjacentHTML("beforeend", '<div class="tarjeta vacio">Todavía no hay facturas.<br>' +
        '<a href="factura.html">Agrega tu primera factura</a> para ver el resumen mensual.</div>');
      return;
    }

    const ultima = facturas[facturas.length - 1];
    const estadoFactura = Calculos.estado(ultima.consumo_m3, limites);
    const mes = Calculos.nombreMes(ultima.mes);

    let alerta = '<div class="alerta ok">Tu último consumo está dentro del límite.</div>';
    if (estadoFactura.clase === "exceso") {
      alerta = '<div class="alerta">Superaste tu límite en ' + mes + ': ' + ultima.consumo_m3 + ' m³ de ' + limites.mensual + ' m³.</div>';
    } else if (estadoFactura.clase === "precaucion") {
      alerta = '<div class="alerta aviso">En ' + mes + ' ya vas en ' + Math.round(estadoFactura.porcentaje) + '% de tu límite mensual.</div>';
    }

    contenido.insertAdjacentHTML("beforeend", alerta +
      '<section class="grid3">' +
        '<article class="tarjeta"><span class="suave">Último consumo</span>' +
          '<strong class="dato">' + ultima.consumo_m3 + ' m³</strong><p class="suave">' + mes + '</p></article>' +
        '<article class="tarjeta"><span class="suave">Promedio mensual</span>' +
          '<strong class="dato">' + Calculos.promedio(facturas).toFixed(1) + ' m³</strong><p class="suave">De ' + facturas.length + ' facturas</p></article>' +
        '<article class="tarjeta"><span class="suave">Estado de la meta</span>' +
          '<strong class="dato color-' + estadoFactura.clase + '">' + estadoFactura.nombre + '</strong>' +
          '<p class="suave">' + Math.round(estadoFactura.porcentaje) + '% de tu límite de ' + limites.mensual + ' m³</p></article>' +
      '</section>' +
      '<section class="grid2">' +
        '<article class="tarjeta"><h3>Consumo mensual (m³)</h3><p class="suave">La línea roja es tu límite</p><div id="g1"></div></article>' +
        '<article class="tarjeta"><h3>Valor de cada factura (miles de $)</h3><div id="g2"></div></article>' +
      '</section>');

    const ultimas = facturas.slice(-6);
    const etiquetas = ultimas.map(function (f) { return f.mes.slice(2); });
    Graficas.linea("#g1", ultimas.map(function (f) { return f.consumo_m3; }), etiquetas, limites.mensual);
    Graficas.barras("#g2", ultimas.map(function (f) { return f.total / 1000; }), etiquetas);
  }

  dibujarFacturas();
  cargarEstado();
})();