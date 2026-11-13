"""Racha, insignias y consejos de ahorro de Water Controller Smart.

Se creó este módulo aparte para no llenar app.py. Son funciones simples que
solo leen la lista de actividades del usuario (la misma que ya se carga de
SQLite) y devuelven diccionarios; no guardan nada nuevo en la base de datos.

- Racha: días seguidos en los que el consumo total quedó dentro de la meta.
- Insignias: logros que se calculan a partir del historial.
- Consejos: recomendaciones basadas en los últimos 14 días de consumo.
"""
from datetime import datetime, timedelta

LITROS_BOTELLA = 1.5          # para las equivalencias ("N botellas de 1,5 L")
DIAS_CONSEJOS = 14            # ventana de días que miran los consejos
MAX_CONSEJOS = 4


def _fecha(texto):
    return datetime.strptime(texto, "%Y-%m-%d").date()


def _coma(numero, decimales=1):
    return f"{numero:.{decimales}f}".replace(".", ",")


def _botellas(litros):
    return max(1, round(litros / LITROS_BOTELLA))


# ---------- Racha ----------

def totales_por_dia(actividades):
    """Suma los litros de cada día: {"2026-11-13": 85.5, ...}."""
    totales = {}
    for a in actividades:
        totales[a["fecha"]] = round(
            totales.get(a["fecha"], 0.0) + a["litros"], 2
        )
    return totales


def calcular_rachas(actividades, meta, hoy=None):
    """Devuelve (racha_actual, mejor_racha).

    Un día cuenta como cumplido si tiene al menos una actividad registrada y
    el total no supera la meta. Un día sin registros rompe la racha, así no
    se puede ganar sin usar la aplicación. Si hoy todavía no hay registros,
    la racha de ayer sigue viva (el día aún no termina).
    """
    hoy = hoy or datetime.now().date()
    totales = totales_por_dia(actividades)
    cumplidos = {
        _fecha(f) for f, litros in totales.items() if litros <= meta
    }

    # Mejor racha de todo el historial
    mejor = 0
    for dia in cumplidos:
        if dia - timedelta(days=1) not in cumplidos:   # inicio de una racha
            largo = 1
            while dia + timedelta(days=largo) in cumplidos:
                largo += 1
            mejor = max(mejor, largo)

    # Racha actual: se cuenta hacia atrás desde hoy (o ayer si hoy está vacío)
    dia = hoy if hoy.isoformat() in totales else hoy - timedelta(days=1)
    actual = 0
    while dia in cumplidos:
        actual += 1
        dia -= timedelta(days=1)

    return actual, max(mejor, actual)


# ---------- Insignias ----------

def _mejor_tramo_sin_exceso(actividades):
    """Mayor cantidad de actividades seguidas sin exceso de tiempo."""
    mejor = actual = 0
    for a in sorted(actividades, key=lambda x: (x["fecha"], x["hora"])):
        if a.get("exceso_tiempo"):
            actual = 0
        else:
            actual += 1
            mejor = max(mejor, actual)
    return mejor


def calcular_insignias(actividades, mejor_racha):
    """Lista de insignias con su progreso. Siempre se muestran todas, las
    que aún no se ganan salen en gris."""
    con_cronometro = sum(1 for a in actividades if a["origen"] == "cronometro")
    tipos = len({a["actividad"] for a in actividades})
    tramo = _mejor_tramo_sin_exceso(actividades)

    definicion = [
        ("primer_paso", "🌱", "Primer paso",
         "Registra tu primera actividad", len(actividades), 1),
        ("explorador", "🧭", "Explorador",
         "Registra 3 tipos de actividad distintos", tipos, 3),
        ("cronometrista", "⏱️", "Cronometrista",
         "Usa el cronómetro 10 veces", con_cronometro, 10),
        ("tiempo_justo", "🎯", "Tiempo justo",
         "10 actividades seguidas sin pasarte del tiempo", tramo, 10),
        ("racha_3", "🔥", "Racha de 3 días",
         "3 días seguidos dentro de tu meta", mejor_racha, 3),
        ("racha_7", "🏅", "Racha de 7 días",
         "7 días seguidos dentro de tu meta", mejor_racha, 7),
        ("racha_30", "🏆", "Racha de 30 días",
         "30 días seguidos dentro de tu meta", mejor_racha, 30),
    ]

    return [
        {
            "id": clave,
            "icono": icono,
            "nombre": nombre,
            "descripcion": descripcion,
            "obtenida": valor >= objetivo,
            "progreso": min(valor, objetivo),
            "objetivo": objetivo,
        }
        for clave, icono, nombre, descripcion, valor, objetivo in definicion
    ]


# ---------- Consejos ----------

def generar_consejos(actividades, meta, porcentaje_aviso, racha_actual,
                     insignias, hoy=None):
    """Hasta 4 consejos con datos reales del usuario (últimos 14 días)."""
    hoy = hoy or datetime.now().date()
    desde = (hoy - timedelta(days=DIAS_CONSEJOS - 1)).isoformat()
    recientes = [a for a in actividades if a["fecha"] >= desde]

    if not recientes:
        return [{
            "icono": "📝",
            "texto": "Registra tus primeras actividades y aquí aparecerán "
                     "consejos hechos con tus propios datos.",
        }]

    # Se agrupa por actividad: veces, litros, minutos y últimos valores
    grupos = {}
    for a in sorted(recientes, key=lambda x: (x["fecha"], x["hora"])):
        g = grupos.setdefault(a["actividad"], {
            "nombre": a["nombre"], "veces": 0, "litros": 0.0, "minutos": 0.0,
        })
        g["veces"] += 1
        g["litros"] += a["litros"]
        g["minutos"] += a["minutos"]
        g["caudal"] = a["caudal"]
        g["recomendado"] = a["tiempo_recomendado"]

    total = sum(g["litros"] for g in grupos.values())
    consejos = []

    # 1) Dónde más se puede ahorrar tiempo (cuánto por semana)
    mejor = None
    for g in grupos.values():
        promedio = g["minutos"] / g["veces"]
        if promedio > g["recomendado"]:
            semanal = (promedio - g["recomendado"]) * g["caudal"] \
                * g["veces"] / (DIAS_CONSEJOS / 7)
            if mejor is None or semanal > mejor[0]:
                mejor = (semanal, g, promedio)
    if mejor:
        semanal, g, promedio = mejor
        consejos.append({
            "icono": "⏳",
            "texto": f"En «{g['nombre']}» dedicas en promedio {_coma(promedio)} "
                     f"min y lo recomendado es {_coma(g['recomendado'])} min. "
                     f"Si la acortas ahorrarías unos {_coma(semanal, 0)} L por "
                     f"semana (≈ {_botellas(semanal)} botellas de "
                     f"{_coma(LITROS_BOTELLA)} L).",
        })

    # 2) Qué actividad concentra más consumo
    if total > 0:
        mayor = max(grupos.values(), key=lambda g: g["litros"])
        consejos.append({
            "icono": "💧",
            "texto": f"{mayor['nombre']} es la actividad que más agua usa: "
                     f"{round(mayor['litros'] / total * 100)}% de tu consumo "
                     f"de los últimos {DIAS_CONSEJOS} días.",
        })

    # 3) Cuánto queda hoy para la meta
    hoy_texto = hoy.isoformat()
    litros_hoy = round(sum(
        a["litros"] for a in actividades if a["fecha"] == hoy_texto
    ), 2)
    if litros_hoy > meta:
        consejos.insert(0, {
            "icono": "🚨",
            "texto": f"Hoy ya superaste tu meta por {_coma(litros_hoy - meta)} L. "
                     "Intenta no sumar más consumo hasta mañana.",
        })
    elif litros_hoy >= meta * porcentaje_aviso / 100:
        consejos.insert(0, {
            "icono": "⚠️",
            "texto": f"Te quedan {_coma(meta - litros_hoy)} L para llegar a tu "
                     f"meta de hoy (≈ {_botellas(meta - litros_hoy)} botellas "
                     f"de {_coma(LITROS_BOTELLA)} L). Piensa bien tu próxima actividad.",
        })

    # 4) Motivación: racha y próxima insignia
    pendientes = [
        i for i in insignias
        if i["id"].startswith("racha_") and not i["obtenida"]
    ]
    if racha_actual >= 2 and pendientes:
        sig = pendientes[0]
        consejos.append({
            "icono": "🔥",
            "texto": f"Llevas {racha_actual} días seguidos dentro de tu meta. "
                     f"Te faltan {sig['objetivo'] - racha_actual} para la "
                     f"insignia «{sig['nombre']}».",
        })
    elif racha_actual >= 2:
        consejos.append({
            "icono": "🏆",
            "texto": f"¡{racha_actual} días seguidos dentro de tu meta! "
                     "Estás cuidando muy bien el agua.",
        })

    if not consejos:
        consejos.append({
            "icono": "✅",
            "texto": "Vas muy bien: tus actividades están dentro del tiempo "
                     "recomendado. Sigue así.",
        })

    return consejos[:MAX_CONSEJOS]


# ---------- Resumen para la API ----------

def resumen(actividades, meta, porcentaje_aviso, hoy=None):
    actual, mejor = calcular_rachas(actividades, meta, hoy)
    insignias = calcular_insignias(actividades, mejor)

    return {
        "ok": True,
        "racha_actual": actual,
        "mejor_racha": mejor,
        "insignias": insignias,
        "consejos": generar_consejos(
            actividades, meta, porcentaje_aviso, actual, insignias, hoy
        ),
    }