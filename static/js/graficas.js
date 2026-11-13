/* graficas.js — gráficas simples en SVG (no usa librerías).
     Graficas.linea("#id", valores, etiquetas, limite)   limite es opcional
     Graficas.barras("#id", valores, etiquetas) */

const Graficas = (function () {
  const ANCHO = 520, ALTO = 210, IZQ = 40, DER = 8, SUP = 10, INF = 26;

  /** Devuelve las funciones que convierten un dato en coordenadas del dibujo. */
  function escalas(valores, conBarras, limite) {
    const maximo = Math.max.apply(null, valores.concat([limite || 0])) * 1.15 || 10;
    const util = ANCHO - IZQ - DER;
    const divisiones = conBarras ? valores.length : Math.max(valores.length - 1, 1);
    return {
      maximo: maximo,
      x: function (i) { return IZQ + (i + (conBarras ? 0.5 : 0)) * util / divisiones; },
      y: function (v) { return ALTO - INF - v / maximo * (ALTO - INF - SUP); },   // en SVG el 0 está arriba
    };
  }

  /** Líneas horizontales de fondo con su número. */
  function cuadricula(e) {
    let svg = "";
    for (let i = 0; i <= 4; i++) {
      const v = e.maximo * i / 4;
      svg += '<line x1="' + IZQ + '" x2="' + (ANCHO - DER) + '" y1="' + e.y(v) + '" y2="' + e.y(v) + '" stroke="#e2e8f0"/>' +
             '<text x="' + (IZQ - 6) + '" y="' + (e.y(v) + 3) + '" text-anchor="end">' + Math.round(v) + '</text>';
    }
    return svg;
  }

  /** Texto debajo de cada dato (el mes). */
  function etiquetasX(etiquetas, e) {
    return etiquetas.map(function (t, i) {
      return '<text x="' + e.x(i) + '" y="' + (ALTO - 8) + '" text-anchor="middle">' + t + '</text>';
    }).join("");
  }

  function pintar(selector, contenido) {
    document.querySelector(selector).innerHTML =
      '<svg class="grafica" viewBox="0 0 ' + ANCHO + ' ' + ALTO + '">' + contenido + '</svg>';
  }

  function linea(selector, valores, etiquetas, limite) {
    const e = escalas(valores, false, limite);
    // "M" mueve el lápiz al primer punto y "L" traza una línea hasta el siguiente
    const trazo = valores.map(function (v, i) { return (i === 0 ? "M" : "L") + e.x(i) + "," + e.y(v); }).join("");
    const puntos = valores.map(function (v, i) {
      return '<circle cx="' + e.x(i) + '" cy="' + e.y(v) + '" r="3.5" fill="#0284c7"/>';
    }).join("");
    const lineaLimite = limite
      ? '<line class="limite" x1="' + IZQ + '" x2="' + (ANCHO - DER) + '" y1="' + e.y(limite) + '" y2="' + e.y(limite) + '"/>'
      : "";
    pintar(selector, cuadricula(e) + lineaLimite +
      '<path d="' + trazo + '" fill="none" stroke="#0284c7" stroke-width="2.5"/>' + puntos + etiquetasX(etiquetas, e));
  }

  function barras(selector, valores, etiquetas) {
    const e = escalas(valores, true);
    const ancho = (ANCHO - IZQ - DER) / valores.length * 0.6;
    const columnas = valores.map(function (v, i) {
      return '<rect x="' + (e.x(i) - ancho / 2) + '" y="' + e.y(v) + '" width="' + ancho +
             '" height="' + (ALTO - INF - e.y(v)) + '" rx="3" fill="#22d3ee"/>';
    }).join("");
    pintar(selector, cuadricula(e) + columnas + etiquetasX(etiquetas, e));
  }

  return { linea: linea, barras: barras };
})();
