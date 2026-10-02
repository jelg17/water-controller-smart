/* panel.js — pantalla principal: alerta, tarjetas y gráficas con las facturas guardadas. */

(function () {
  const contenido = document.getElementById("contenido");
  const facturas = Almacen.listarFacturas();
  const limites = Almacen.obtenerLimites();

  // Si no hay facturas, explicamos cómo agregarlas
  if (facturas.length === 0) {
    contenido.innerHTML = '<div class="tarjeta vacio">Todavía no hay facturas.<br>' +
      '<a href="factura.html">Agrega tu primera factura</a> para ver tu panel.</div>';
    return;
  }

  const ultima = facturas[facturas.length - 1];
  const estado = Calculos.estado(ultima.consumo_m3, limites);
  const mes = Calculos.nombreMes(ultima.mes);

  // Mensaje de la alerta según el estado
  let alerta = '<div class="alerta ok">Tu último consumo está dentro del límite.</div>';
  if (estado.clase === "exceso") {
    alerta = '<div class="alerta">Superaste tu límite en ' + mes + ': ' + ultima.consumo_m3 + ' m³ de ' + limites.mensual + ' m³.</div>';
  } else if (estado.clase === "precaucion") {
    alerta = '<div class="alerta aviso">En ' + mes + ' ya vas en ' + Math.round(estado.porcentaje) + '% de tu límite mensual.</div>';
  }

  contenido.innerHTML = alerta +
    '<section class="grid3">' +
      '<article class="tarjeta"><span class="suave">Último consumo</span>' +
        '<strong class="dato">' + ultima.consumo_m3 + ' m³</strong><p class="suave">' + mes + '</p></article>' +
      '<article class="tarjeta"><span class="suave">Promedio mensual</span>' +
        '<strong class="dato">' + Calculos.promedio(facturas).toFixed(1) + ' m³</strong><p class="suave">De ' + facturas.length + ' facturas</p></article>' +
      '<article class="tarjeta"><span class="suave">Estado de la meta</span>' +
        '<strong class="dato color-' + estado.clase + '">' + estado.nombre + '</strong>' +
        '<p class="suave">' + Math.round(estado.porcentaje) + '% de tu límite de ' + limites.mensual + ' m³</p></article>' +
    '</section>' +
    '<section class="grid2">' +
      '<article class="tarjeta"><h3>Consumo mensual (m³)</h3><p class="suave">La línea roja es tu límite</p><div id="g1"></div></article>' +
      '<article class="tarjeta"><h3>Valor de cada factura (miles de $)</h3><div id="g2"></div></article>' +
    '</section>';

  // Gráficas: las últimas 6 facturas
  const ultimas = facturas.slice(-6);
  const etiquetas = ultimas.map(function (f) { return f.mes.slice(2); });
  Graficas.linea("#g1", ultimas.map(function (f) { return f.consumo_m3; }), etiquetas, limites.mensual);
  Graficas.barras("#g2", ultimas.map(function (f) { return f.total / 1000; }), etiquetas);
})();
