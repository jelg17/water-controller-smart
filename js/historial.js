/* historial.js — tabla y gráfica con todas las facturas, y botón para exportar a CSV. */

(function () {
  const contenido = document.getElementById("contenido");
  const facturas = Almacen.listarFacturas();
  const limites = Almacen.obtenerLimites();

  if (facturas.length === 0) {
    contenido.innerHTML = '<div class="tarjeta vacio">No hay registros todavía. ' +
      '<a href="factura.html">Agrega una factura</a>.</div>';
    return;
  }

  // Una fila de la tabla por factura (la más reciente primero)
  const filas = facturas.slice().reverse().map(function (f) {
    const estado = Calculos.estado(f.consumo_m3, limites);
    return '<tr><td>' + Calculos.nombreMes(f.mes) + '</td><td>' + f.consumo_m3 + ' m³</td>' +
           '<td>' + Calculos.pesos(f.total) + '</td><td>' + Math.round(estado.porcentaje) + '%</td>' +
           '<td><span class="etiqueta ' + estado.clase + '">' + estado.nombre + '</span></td></tr>';
  }).join("");

  contenido.innerHTML =
    '<div><button class="boton" id="exportar">Exportar CSV</button></div>' +
    '<article class="tarjeta"><h3>Tendencia de consumo (m³)</h3><div id="g1"></div></article>' +
    '<article class="tarjeta"><h3>Registros</h3><table class="tabla"><thead><tr>' +
      '<th>Mes</th><th>Consumo</th><th>Total</th><th>% del límite</th><th>Estado</th></tr></thead>' +
      '<tbody>' + filas + '</tbody></table></article>';

  Graficas.linea("#g1", facturas.map(function (f) { return f.consumo_m3; }),
                 facturas.map(function (f) { return f.mes.slice(2); }), limites.mensual);

  // Exportar: arma el texto del CSV y le pide al navegador que lo descargue
  document.getElementById("exportar").addEventListener("click", function () {
    const lineas = ["mes,consumo_m3,total"].concat(
      facturas.map(function (f) { return f.mes + "," + f.consumo_m3 + "," + f.total; }));
    const enlace = document.createElement("a");
    enlace.href = URL.createObjectURL(new Blob([lineas.join("\n")], { type: "text/csv" }));
    enlace.download = "mis_facturas.csv";
    enlace.click();
  });
})();
