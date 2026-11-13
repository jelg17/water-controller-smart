"""Resumen semanal de consumo (para el panel y para enviar por correo).

Se creó este módulo aparte, igual que logros.py: son funciones que solo leen
la lista de actividades del usuario y devuelven datos o texto, sin tocar la
base de datos.

La "semana" son los últimos 7 días contando hoy, y se compara con los 7 días
anteriores a esos.
"""
from datetime import datetime, timedelta
from html import escape

import logros

DIAS = ["lun", "mar", "mié", "jue", "vie", "sáb", "dom"]
LITROS_BOTELLA = 1.5


def _coma(numero, decimales=1):
    return f"{numero:.{decimales}f}".replace(".", ",")


def _fecha(texto):
    return datetime.strptime(texto, "%Y-%m-%d").date()


def _etiqueta(fecha_texto):
    d = _fecha(fecha_texto)
    return f"{DIAS[d.weekday()]} {d.day}"


def calcular_resumen(actividades, meta, hoy=None):
    """Arma todas las cifras de la semana en un diccionario."""
    hoy = hoy or datetime.now().date()
    inicio = hoy - timedelta(days=6)
    inicio_previo = inicio - timedelta(days=7)

    totales = logros.totales_por_dia(actividades)
    semana = [a for a in actividades if inicio.isoformat() <= a["fecha"] <= hoy.isoformat()]
    previa = [
        a for a in actividades
        if inicio_previo.isoformat() <= a["fecha"] < inicio.isoformat()
    ]

    # Un renglón por día (con 0 si no hubo registros) para la gráfica de barras
    por_dia = []
    for i in range(7):
        dia = (inicio + timedelta(days=i)).isoformat()
        por_dia.append({
            "fecha": dia,
            "etiqueta": _etiqueta(dia),
            "litros": totales.get(dia, 0.0),
            "con_registros": dia in totales,
        })

    total = round(sum(a["litros"] for a in semana), 2)
    total_previo = round(sum(a["litros"] for a in previa), 2)
    variacion = (
        round((total - total_previo) / total_previo * 100, 1)
        if total_previo > 0 else None
    )

    con_registros = [d for d in por_dia if d["con_registros"]]
    mejor = min(con_registros, key=lambda d: d["litros"]) if con_registros else None
    peor = max(con_registros, key=lambda d: d["litros"]) if con_registros else None

    # Actividad que más agua usó en la semana
    por_actividad = {}
    for a in semana:
        por_actividad[a["nombre"]] = por_actividad.get(a["nombre"], 0.0) + a["litros"]
    top = None
    if por_actividad:
        nombre = max(por_actividad, key=por_actividad.get)
        top = {
            "nombre": nombre,
            "litros": round(por_actividad[nombre], 2),
            "porcentaje": round(por_actividad[nombre] / total * 100) if total else 0,
        }

    racha_actual, _ = logros.calcular_rachas(actividades, meta, hoy)
    ahorro = round(sum(a.get("ahorro_litros", 0.0) for a in semana), 2)

    return {
        "desde": inicio.isoformat(),
        "hasta": hoy.isoformat(),
        "meta": meta,
        "total_litros": total,
        "total_previo": total_previo,
        "variacion": variacion,
        "promedio_diario": round(total / 7, 2),
        "dias_con_registros": len(con_registros),
        "dias_en_meta": sum(1 for d in con_registros if d["litros"] <= meta),
        "mejor_dia": mejor,
        "peor_dia": peor,
        "actividad_top": top,
        "ahorro_potencial": ahorro,
        "racha_actual": racha_actual,
        "num_actividades": len(semana),
        "por_dia": por_dia,
        "sin_datos": len(semana) == 0,
    }


def construir_texto(r):
    """Versión en texto plano del correo (para programas sin HTML)."""
    lineas = [
        "Tu resumen semanal de Water Controller Smart",
        f"Del {r['desde']} al {r['hasta']}",
        "",
        f"Consumo total: {_coma(r['total_litros'])} L",
    ]
    if r["variacion"] is not None:
        signo = "+" if r["variacion"] > 0 else ""
        lineas.append(f"Frente a la semana anterior: {signo}{_coma(r['variacion'])}%")
    lineas += [
        f"Promedio diario: {_coma(r['promedio_diario'])} L (tu meta es {_coma(r['meta'])} L)",
        f"Días dentro de la meta: {r['dias_en_meta']} de {r['dias_con_registros']} con registros",
    ]
    if r["mejor_dia"]:
        lineas.append(
            f"Mejor día: {r['mejor_dia']['etiqueta']} ({_coma(r['mejor_dia']['litros'])} L)"
        )
    if r["actividad_top"]:
        lineas.append(
            f"Actividad que más agua usó: {r['actividad_top']['nombre']} "
            f"({r['actividad_top']['porcentaje']}%)"
        )
    lineas.append(f"Racha actual: {r['racha_actual']} días dentro de la meta")
    return "\n".join(lineas)


def construir_html(r):
    """Se creó la plantilla HTML del resumen (tablas y estilos en línea,
    igual que el correo de alertas, para que se vea bien en Gmail y Outlook)."""
    # Variación frente a la semana anterior: bajar el consumo es bueno (verde)
    if r["variacion"] is None:
        variacion = "Sin semana anterior para comparar"
        color_var = "#64748b"
    else:
        sube = r["variacion"] > 0
        flecha = "▲" if sube else "▼"
        signo = "+" if sube else ""
        variacion = f"{flecha} {signo}{_coma(r['variacion'])}% vs semana anterior"
        color_var = "#dc3545" if sube else "#28a745"

    # Barras por día: el ancho es proporcional al día de mayor consumo
    maximo = max([d["litros"] for d in r["por_dia"]] + [r["meta"]]) or 1
    barras = ""
    for d in r["por_dia"]:
        ancho = max(2, round(d["litros"] / maximo * 100)) if d["litros"] else 0
        color = "#dc3545" if d["litros"] > r["meta"] else "#0284c7"
        barras += f"""
          <tr>
            <td style="width:56px;font-size:12px;color:#64748b;padding:4px 0;">{escape(d['etiqueta'])}</td>
            <td style="padding:4px 0;">
              <div style="background:{color};height:14px;width:{ancho}%;border-radius:4px;"></div>
            </td>
            <td style="width:70px;text-align:right;font-size:12px;color:#0f172a;padding:4px 0;">{_coma(d['litros'])} L</td>
          </tr>"""

    detalles = ""
    if r["mejor_dia"]:
        detalles += f"<li>Mejor día: <strong>{escape(r['mejor_dia']['etiqueta'])}</strong> ({_coma(r['mejor_dia']['litros'])} L)</li>"
    if r["actividad_top"]:
        detalles += (f"<li>Lo que más agua usó: <strong>{escape(r['actividad_top']['nombre'])}</strong> "
                     f"({r['actividad_top']['porcentaje']}% de tu consumo)</li>")
    if r["ahorro_potencial"] > 0:
        botellas = max(1, round(r["ahorro_potencial"] / LITROS_BOTELLA))
        detalles += (f"<li>Pudiste ahorrar unos <strong>{_coma(r['ahorro_potencial'], 0)} L</strong> "
                     f"(≈ {botellas} botellas de {_coma(LITROS_BOTELLA)} L) respetando los tiempos recomendados</li>")
    detalles += f"<li>Racha actual: <strong>🔥 {r['racha_actual']}</strong> días dentro de tu meta</li>"

    return f"""\
<!doctype html>
<html lang="es">
<body style="margin:0;padding:0;background:#f1f5f9;">
  <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:#f1f5f9;padding:24px 12px;">
    <tr><td align="center">
      <table role="presentation" width="560" cellpadding="0" cellspacing="0" style="max-width:560px;width:100%;background:#ffffff;border-radius:12px;overflow:hidden;border:1px solid #e2e8f0;font-family:Arial,Helvetica,sans-serif;">

        <tr><td style="background:#0c4a6e;padding:20px 28px;color:#ffffff;">
          <div style="font-size:20px;font-weight:bold;">💧 Water Controller Smart</div>
          <div style="font-size:13px;color:#94c7e8;margin-top:4px;">Tu resumen semanal · {escape(r['desde'])} al {escape(r['hasta'])}</div>
        </td></tr>

        <tr><td style="padding:28px 28px 8px 28px;">
          <table role="presentation" width="100%" cellpadding="0" cellspacing="0"><tr>
            <td style="width:40%;vertical-align:top;">
              <div style="font-size:12px;color:#64748b;">Consumo total</div>
              <div style="font-size:26px;font-weight:bold;color:#0f172a;">{_coma(r['total_litros'])} L</div>
              <div style="font-size:12px;color:{color_var};font-weight:bold;">{variacion}</div>
            </td>
            <td style="width:30%;vertical-align:top;">
              <div style="font-size:12px;color:#64748b;">Promedio diario</div>
              <div style="font-size:26px;font-weight:bold;color:#0f172a;">{_coma(r['promedio_diario'], 0)} L</div>
              <div style="font-size:12px;color:#64748b;">Meta: {_coma(r['meta'], 0)} L</div>
            </td>
            <td style="width:30%;vertical-align:top;">
              <div style="font-size:12px;color:#64748b;">Dentro de la meta</div>
              <div style="font-size:26px;font-weight:bold;color:#0f172a;">{r['dias_en_meta']} de {r['dias_con_registros']}</div>
              <div style="font-size:12px;color:#64748b;">días con registros</div>
            </td>
          </tr></table>
        </td></tr>

        <tr><td style="padding:16px 28px;">
          <div style="font-size:14px;font-weight:bold;color:#0f172a;margin-bottom:6px;">Consumo por día</div>
          <table role="presentation" width="100%" cellpadding="0" cellspacing="0">{barras}
          </table>
          <div style="font-size:11px;color:#64748b;margin-top:6px;">Las barras rojas superaron tu meta diaria.</div>
        </td></tr>

        <tr><td style="padding:0 28px 24px 28px;">
          <ul style="margin:0;padding-left:20px;font-size:14px;color:#334155;line-height:1.7;">{detalles}
          </ul>
        </td></tr>

        <tr><td style="background:#f8fafc;border-top:1px solid #e2e8f0;padding:16px 28px;font-size:12px;color:#64748b;line-height:1.5;">
          Pediste este resumen desde tu panel de Water Controller Smart.
          Puedes ajustar tu meta diaria y tus tiempos recomendados en Configuración.
        </td></tr>

      </table>
    </td></tr>
  </table>
</body>
</html>
"""