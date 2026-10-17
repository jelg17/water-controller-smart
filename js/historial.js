/* historial.js — Implementación completa de US-005 y US-006:
   - Filtro por periodo (7 días, 30 días, todo el historial, rango personalizado).
   - Cambio dinámico de gráfico (Barras / Línea SVG).
   - Comparativa porcentual entre periodos y metas de consumo.
   - Reporte exportable a CSV.
*/

(function () {
  const contenido = document.getElementById("contenido");

  contenido.innerHTML =
    '<section class="tarjeta formulario">' +
      '<h3>Consulta y Filtros de Consumo (US-005)</h3>' +
      '<div class="grid2" style="align-items:flex-end;">' +
        '<label class="campo">Vistas Rápidas ' +
          '<select id="selVista">' +
            '<option value="7dias">Últimos 7 días</option>' +
            '<option value="30dias">Últimos 30 días</option>' +
            '<option value="todo">Todo el historial</option>' +
            '<option value="personalizado">Rango Personalizado</option>' +
          '</select>' +
        '</label>' +
        '<label class="campo">Tipo de Gráfico ' +
          '<select id="selGrafico">' +
            '<option value="barras">Gráfico de Barras</option>' +
            '<option value="linea">Gráfico de Línea</option>' +
          '</select>' +
        '</label>' +
      '</div>' +
      '<div id="secPersonalizada" class="grid3" style="display:none; margin-top:10px;">' +
        '<label class="campo">Desde <input type="date" id="filtroDesde"></label>' +
        '<label class="campo">Hasta <input type="date" id="filtroHasta"></label>' +
        '<div style="display:flex; align-items:flex-end;">' +
          '<button class="boton" id="btnFiltrar">Aplicar Rango</button>' +
        '</div>' +
      '</div>' +
    '</section>' +

    '<section class="grid3" id="tarjetasResumen"></section>' +

    '<section class="grid2">' +
      '<article class="tarjeta">' +
        '<h3>Consumo diario en litros (L)</h3>' +
        '<p class="suave" id="subtiGrafico">Comportamiento del gasto hídrico</p>' +
        '<div id="graficoDiario"></div>' +
      '</article>' +
      '<article class="tarjeta">' +
        '<h3>Resumen por Actividad</h3>' +
        '<p class="suave">Desglose de minutos y litros consumidos</p>' +
        '<div id="tablaActividades"></div>' +
      '</article>' +
    '</section>' +

    '<article class="tarjeta">' +
      '<div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:12px; flex-wrap:wrap; gap:10px;">' +
        '<div>' +
          '<h3>Historial Detallado de Actividades</h3>' +
          '<p class="suave">Registros capturados por cronómetro e ingreso manual</p>' +
        '</div>' +
        '<button class="boton" id="btnExportarCSV">📥 Exportar Reporte (CSV)</button>' +
      '</div>' +
      '<div id="tablaHistorial"></div>' +
    '</article>' +

    '<article class="tarjeta">' +
      '<h3>Facturas Mensuales de Servicio (m³)</h3>' +
      '<div id="tablaFacturas"></div>' +
    '</article>';

  const selVista = document.getElementById("selVista");
  const selGrafico = document.getElementById("selGrafico");
  const secPersonalizada = document.getElementById("secPersonalizada");
  const filtroDesde = document.getElementById("filtroDesde");
  const filtroHasta = document.getElementById("filtroHasta");
  const btnFiltrar = document.getElementById("btnFiltrar");
  const btnExportarCSV = document.getElementById("btnExportarCSV");

  const tarjetasResumen = document.getElementById("tarjetasResumen");
  const graficoDiario = document.getElementById("graficoDiario");
  const tablaActividades = document.getElementById("tablaActividades");
  const tablaHistorial = document.getElementById("tablaHistorial");
  const tablaFacturas = document.getElementById("tablaFacturas");

  let datosActuales = null;

  function coma(num) {
    return String(num).replace(".", ",");
  }

  function litros(val) {
    return val.toLocaleString("es-CO", { minimumFractionDigits: 1, maximumFractionDigits: 1 }) + " L";
  }

  function cargarHistorial() {
    const vista = selVista.value;
    let url = "/api/historial?vista=" + encodeURIComponent(vista);
    if (vista === "personalizado" && filtroDesde.value && filtroHasta.value) {
      url += "&desde=" + encodeURIComponent(filtroDesde.value) + "&hasta=" + encodeURIComponent(filtroHasta.value);
    }

    fetch(url)
      .then(function (res) { return res.json(); })
      .then(function (res) {
        if (!res.ok) return;
        datosActuales = res;
        dibujarTodo(res);
      })
      .catch(function () {
        tarjetasResumen.innerHTML = '<div class="alerta error">No se pudo conectar con el servidor Python.</div>';
      });
  }

  function dibujarTodo(res) {
    // 1. Tarjetas de Resumen, Comparativa y Cumplimiento de Metas (US-006)
    const comp = res.comparativa;
    let txtVar = "Sin periodo previo";
    if (comp.total_previo > 0) {
      const signo = comp.variacion_porcentual > 0 ? "+" : "";
      txtVar = signo + comp.variacion_porcentual + "% vs periodo anterior";
    }

    tarjetasResumen.innerHTML =
      '<article class="tarjeta">' +
        '<span class="suave">Consumo Total</span>' +
        '<strong class="dato">' + litros(res.total_litros) + '</strong>' +
        '<p class="suave">' + txtVar + '</p>' +
      '</article>' +
      '<article class="tarjeta">' +
        '<span class="suave">Litros Ahorrados</span>' +
        '<strong class="dato color-normal">' + litros(res.total_ahorro) + '</strong>' +
        '<p class="suave">Frente al tiempo recomendado</p>' +
      '</article>' +
      '<article class="tarjeta">' +
        '<span class="suave">Cumplimiento de Meta</span>' +
        '<strong class="dato">' + res.cumplimiento_metas.porcentaje + '%</strong>' +
        '<p class="suave">' + res.cumplimiento_metas.dias_cumplidos + ' de ' + res.dias_totales + ' días en regla (<=100L)</p>' +
      '</article>';

    // 2. Consulta Vacía (US-005)
    if (res.num_registros === 0 && res.total_litros === 0) {
      graficoDiario.innerHTML = '<div class="vacio">No hay registros de consumo para el rango de fechas seleccionado.</div>';
      tablaActividades.innerHTML = '<div class="vacio">Sin datos.</div>';
      tablaHistorial.innerHTML = '<div class="vacio">No hay actividades registradas en este periodo.</div>';
      dibujarFacturas();
      return;
    }

    // 3. Renderizado del Gráfico (Barras / Líneas SVG)
    dibujarGrafico(res);

    // 4. Desglose por Actividad
    let htmlAct = '<table class="tabla"><thead><tr><th>Actividad</th><th>Veces</th><th>Tiempo</th><th>Consumo</th><th>Ahorro Potencial</th></tr></thead><tbody>';
    for (const act in res.por_actividad) {
      const item = res.por_actividad[act];
      htmlAct += '<tr><td>' + act + '</td><td>' + item.cantidad + '</td><td>' + coma(item.minutos) + ' min</td>' +
                 '<td><strong>' + litros(item.litros) + '</strong></td><td>' + (item.ahorro > 0 ? litros(item.ahorro) : '—') + '</td></tr>';
    }
    htmlAct += '</tbody></table>';
    tablaActividades.innerHTML = htmlAct;

    // 5. Tabla de Historial Detallado
    let htmlTabla = '<table class="tabla"><thead><tr><th>Fecha</th><th>Hora</th><th>Actividad</th><th>Duración</th><th>Caudal</th><th>Litros</th><th>Ahorro</th><th>Origen</th></tr></thead><tbody>';
    res.actividades.forEach(function (a) {
      htmlTabla += '<tr><td>' + a.fecha + '</td><td>' + a.hora.slice(0, 5) + '</td><td>' + a.nombre + '</td>' +
                   '<td>' + coma(a.minutos) + ' min</td><td>' + coma(a.caudal) + ' L/min</td>' +
                   '<td><strong>' + litros(a.litros) + '</strong></td>' +
                   '<td>' + (a.ahorro_litros > 0 ? '<span class="color-normal">' + litros(a.ahorro_litros) + '</span>' : '—') + '</td>' +
                   '<td>' + (a.origen === 'cronometro' ? '⏱️ Cronómetro' : '📝 Manual') + '</td></tr>';
    });
    htmlTabla += '</tbody></table>';
    tablaHistorial.innerHTML = htmlTabla;

    dibujarFacturas();
  }

  function dibujarGrafico(res) {
    if (!res || !res.grafico_fechas || res.grafico_fechas.valores.length === 0) {
      graficoDiario.innerHTML = '<div class="vacio">Sin datos para graficar.</div>';
      return;
    }
    const tipo = selGrafico.value;
    if (tipo === "linea") {
      Graficas.linea("#graficoDiario", res.grafico_fechas.valores, res.grafico_fechas.etiquetas, 100);
    } else {
      Graficas.barras("#graficoDiario", res.grafico_fechas.valores, res.grafico_fechas.etiquetas);
    }
  }

  function dibujarFacturas() {
    const facturas = Almacen.listarFacturas();
    if (facturas.length === 0) {
      tablaFacturas.innerHTML = '<p class="suave">No hay facturas guardadas en la demostración.</p>';
      return;
    }
    const filas = facturas.slice().reverse().map(function (f) {
      return '<tr><td>' + Calculos.nombreMes(f.mes) + '</td><td>' + f.consumo_m3 + ' m³</td><td>' + Calculos.pesos(f.total) + '</td></tr>';
    }).join("");
    tablaFacturas.innerHTML = '<table class="tabla"><thead><tr><th>Mes</th><th>Consumo</th><th>Total</th></tr></thead><tbody>' + filas + '</tbody></table>';
  }

  // Eventos
  selVista.addEventListener("change", function () {
    if (selVista.value === "personalizado") {
      secPersonalizada.style.display = "grid";
    } else {
      secPersonalizada.style.display = "none";
      cargarHistorial();
    }
  });

  selGrafico.addEventListener("change", function () {
    if (datosActuales) dibujarGrafico(datosActuales);
  });

  btnFiltrar.addEventListener("click", cargarHistorial);

  btnExportarCSV.addEventListener("click", function () {
    if (!datosActuales || !datosActuales.actividades.length) {
      alert("No hay registros disponibles para exportar en este período.");
      return;
    }
    const encabezado = ["ID,Fecha,Hora,Actividad,Duracion_Min,Caudal_Lmin,Litros,Ahorro_Litros,Origen"];
    const filas = datosActuales.actividades.map(function (a) {
      return [a.id, a.fecha, a.hora, '"' + a.nombre + '"', a.minutos, a.caudal, a.litros, a.ahorro_litros, a.origen].join(",");
    });
    const contenidoCSV = encabezado.concat(filas).join("\n");
    const blob = new Blob([contenidoCSV], { type: "text/csv;charset=utf-8;" });
    const enlace = document.createElement("a");
    enlace.href = URL.createObjectURL(blob);
    enlace.download = "reporte_consumo_agua_water_controller.csv";
    enlace.click();
  });

  // Carga inicial
  cargarHistorial();
})();