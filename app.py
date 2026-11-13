"""Servidor de Water Controller Smart.

US-001: Registrar actividades.
US-002: Calcular consumo de agua.
US-003: Detectar excesos de tiempo y de consumo diario.
US-004: Alertas por la aplicación web y por correo electrónico.
US-005: Consultar historial y estadísticas.
US-006: Reportes de ahorro y comparativas.
US-007: Personalizar caudal y tiempo recomendado.
US-008: Configurar la meta diaria de consumo.

Se migró el servidor a Flask: las páginas se entregan desde `templates/`,
los estilos y scripts desde `static/`, y los datos ya no se guardan en
datos.json sino en SQLite (ver db.py). Cada persona inicia sesión y todo
lo que guarda queda ligado a su usuario.
"""
import functools
import math
import os
import re
import secrets
import threading
import time
import webbrowser
from datetime import datetime, timedelta

from flask import (
    Flask, g, jsonify, redirect, render_template, request, session,
    url_for,
)
from werkzeug.security import check_password_hash, generate_password_hash
from dotenv import load_dotenv  

import db
from correo import enviar_correo

load_dotenv()   # lee el archivo .env y carga las variables WCS_SMTP_*


PUERTO = 7500

MAX_MINUTOS = 1440
META_DIARIA_PREDETERMINADA = 100.0
PORCENTAJE_AVISO_META = 80
MAX_PERSONALIZADAS = 20
MAX_NOMBRE = 40
MAX_CAUDAL = 200

CATALOGO = {
    "ducha": {
        "nombre": "Ducha",
        "caudal": 9.0,
        "tiempo_recomendado": 5,
    },
    "platos": {
        "nombre": "Lavado de platos",
        "caudal": 6.0,
        "tiempo_recomendado": 10,
    },
    "riego": {
        "nombre": "Riego",
        "caudal": 12.0,
        "tiempo_recomendado": 15,
    },
    "aseo": {
        "nombre": "Aseo",
        "caudal": 8.0,
        "tiempo_recomendado": 10,
    },
}

ERROR_DURACION = (
    "La duración no es válida: escribe un número de minutos mayor que cero."
)

# Se definieron los estados del día para US-003 y su etiqueta en pantalla.
ESTADOS_DIA = {
    "normal": "Normal",
    "precaucion": "Precaución",
    "exceso": "Exceso",
}

MIN_CONTRASENA = 6
PATRON_CORREO = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")

# ---------- Aplicación Flask ----------

app = Flask(__name__)

# Se creó la llave que firma la sesión. Si no se define WCS_SECRET_KEY se
# genera una al arrancar (las sesiones se cierran al reiniciar el servidor).
app.config["SECRET_KEY"] = (
    os.environ.get("WCS_SECRET_KEY") or secrets.token_hex(32)
)
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
app.config["MAX_CONTENT_LENGTH"] = 10_000   # mismo tope que tenía el servidor anterior
app.json.ensure_ascii = False
db.iniciar_bd(app)


def a_numero(texto):
    try:
        numero = float(str(texto).strip().replace(",", "."))
    except (ValueError, TypeError):
        return None
    return numero if math.isfinite(numero) else None


def texto_numero(valor, decimales=1):
    return f"{valor:.{decimales}f}".replace(".", ",")


def texto_minutos(minutos):
    return f"{round(minutos, 2):g}".replace(".", ",")


def validar_duracion(texto):
    minutos = a_numero(texto)
    if minutos is not None:
        minutos = round(minutos, 2)

    if minutos is None or minutos <= 0 or minutos > MAX_MINUTOS:
        return None, ERROR_DURACION

    return minutos, None

def es_propia(actividad):
    """Las actividades creadas por el usuario tienen ids que empiezan con p_."""
    return isinstance(actividad, str) and actividad.startswith("p_")


def base_de(datos, actividad):
    """Nombre, caudal y tiempo base de una actividad (estándar o propia)."""
    if actividad in CATALOGO:
        return CATALOGO[actividad]
    return datos.get("personalizadas", {}).get(actividad)


def validar_actividad(datos, actividad):
    if not isinstance(actividad, str):
        return "Elige una actividad válida."

    if actividad in CATALOGO:
        return None

    propia = datos.get("personalizadas", {}).get(actividad)
    if propia and propia["activa"]:
        return None

    return "Elige una actividad válida."


def caudal_de(datos, actividad):
    personalizado = datos.get("caudales", {}).get(actividad)

    if personalizado is not None:
        return personalizado, True

    return base_de(datos, actividad)["caudal"], False


def tiempo_recomendado_de(datos, actividad):
    personalizado = datos.get("tiempos_recomendados", {}).get(actividad)

    if personalizado is not None:
        return personalizado, True

    return base_de(datos, actividad)["tiempo_recomendado"], False


def meta_diaria_de(datos):
    meta = a_numero(datos.get("meta_diaria"))

    if meta is None or meta <= 0:
        return META_DIARIA_PREDETERMINADA

    return meta


def porcentaje_aviso_de(datos):
    """Se implementó el % de la meta a partir del cual hay precaución."""
    porcentaje = a_numero(datos.get("porcentaje_aviso"))

    if porcentaje is None or not 1 <= porcentaje <= 100:
        return PORCENTAJE_AVISO_META

    return porcentaje


def calcular_litros(minutos, caudal):
    return round(minutos * caudal, 2)


def calcular_ahorro(minutos, caudal, tiempo_recomendado):
    return round(max(0.0, minutos - tiempo_recomendado) * caudal, 2)


# ---------- US-003: Detección de excesos ----------

def hay_exceso_de_tiempo(minutos, tiempo_recomendado):
    """Escenario 1: la actividad dura más que el tiempo recomendado."""
    return minutos > tiempo_recomendado


def estado_del_dia(total_litros, meta, porcentaje_aviso):
    """Escenarios 2, 3 y 4 de US-003.

    - exceso: la suma de litros del día supera la meta diaria.
    - precaucion: el consumo ya llegó al % de aviso de la meta.
    - normal: el consumo está por debajo y no se marca nada.
    """
    if total_litros > meta:
        return "exceso"

    if total_litros >= meta * porcentaje_aviso / 100:
        return "precaucion"

    return "normal"


def armar_mensaje(registro):
    recomendado = registro["tiempo_recomendado"]

    mensaje = (
        f"{registro['nombre']}: gastaste "
        f"{texto_numero(registro['litros'])} L "
        f"({texto_minutos(registro['minutos'])} min a "
        f"{texto_numero(registro['caudal'])} L/min)."
    )

    if registro["ahorro_litros"] > 0:
        mensaje += (
            f" Si hubiera durado el tiempo recomendado "
            f"({texto_minutos(recomendado)} min), "
            f"te habrías ahorrado "
            f"{texto_numero(registro['ahorro_litros'])} L."
        )
    else:
        mensaje += (
            f" Estás dentro del tiempo recomendado "
            f"({texto_minutos(recomendado)} min)."
        )

    return mensaje


def crear_registro(usuario_id, datos, actividad, minutos, origen, momento):
    caudal, caudal_personalizado = caudal_de(datos, actividad)
    recomendado, _ = tiempo_recomendado_de(datos, actividad)

    registro = {
        "actividad": actividad,
        "nombre": base_de(datos, actividad)["nombre"],
        "fecha": momento.strftime("%Y-%m-%d"),
        "hora": momento.strftime("%H:%M:%S"),
        "minutos": minutos,
        "caudal": caudal,
        "caudal_personalizado": caudal_personalizado,
        "litros": calcular_litros(minutos, caudal),
        "tiempo_recomendado": recomendado,
        "ahorro_litros": calcular_ahorro(
            minutos, caudal, recomendado
        ),
        "origen": origen,
        # US-003: se marca la actividad si dura más de lo recomendado.
        "exceso_tiempo": hay_exceso_de_tiempo(minutos, recomendado),
    }

    registro["mensaje"] = armar_mensaje(registro)

    # Se guarda en SQLite y la base entrega el id; luego se agrega a la
    # lista en memoria para que los resúmenes del día lo incluyan.
    registro["id"] = db.insertar_actividad(usuario_id, registro)
    datos["actividades"].append(registro)

    return registro


def resumen_del_dia(datos, fecha):
    del_dia = [
        actividad
        for actividad in datos["actividades"]
        if actividad["fecha"] == fecha
    ]

    total = round(sum(a["litros"] for a in del_dia), 2)
    meta = meta_diaria_de(datos)
    estado = estado_del_dia(total, meta, porcentaje_aviso_de(datos))

    return {
        "fecha": fecha,
        "total_litros": total,
        "cantidad": len(del_dia),
        "actividades": del_dia,
        # US-003: estado del día para pintarlo en verde, amarillo o rojo.
        "estado": estado,
        "estado_nombre": ESTADOS_DIA[estado],
    }


def estado_completo(datos):
    catalogo = []

    for clave, info in CATALOGO.items():
        caudal, caudal_personalizado = caudal_de(datos, clave)
        tiempo, tiempo_personalizado = tiempo_recomendado_de(
            datos, clave
        )

        catalogo.append({
            "id": clave,
            "nombre": info["nombre"],
            "caudal": caudal,
            "caudal_estandar": info["caudal"],
            "personalizado": caudal_personalizado,
            "tiempo_recomendado": tiempo,
            "tiempo_recomendado_estandar": info["tiempo_recomendado"],
            "tiempo_personalizado": tiempo_personalizado,
            "propia": False,
        })

    for clave, info in datos.get("personalizadas", {}).items():
        if not info["activa"]:
            continue

        catalogo.append({
            "id": clave,
            "nombre": info["nombre"],
            "caudal": info["caudal"],
            "caudal_estandar": info["caudal"],
            "personalizado": False,
            "tiempo_recomendado": info["tiempo_recomendado"],
            "tiempo_recomendado_estandar": info["tiempo_recomendado"],
            "tiempo_personalizado": False,
            "propia": True,
        })

    cronometro = None

    if datos.get("cronometro"):
        actividad = datos["cronometro"]["actividad"]
        cronometro = {
            "actividad": actividad,
            "nombre": base_de(datos, actividad)["nombre"],
            "segundos": round(
                time.time() - datos["cronometro"]["inicio"], 1
            ),
        }

    meta = meta_diaria_de(datos)
    hoy = resumen_del_dia(
        datos, datetime.now().strftime("%Y-%m-%d")
    )
    porcentaje = round(hoy["total_litros"] / meta * 100, 1)

    hoy["meta_diaria"] = meta
    hoy["porcentaje_meta"] = porcentaje
    hoy["meta_superada"] = hoy["estado"] == "exceso"
    hoy["meta_cercana"] = hoy["estado"] == "precaucion"

    return {
        "ok": True,
        "catalogo": catalogo,
        "cronometro": cronometro,
        "meta_diaria": meta,
        "porcentaje_aviso": porcentaje_aviso_de(datos),
        "hoy": hoy,
    }


# ---------- US-004: Alertas por la web y por correo ----------

def generar_alertas(usuario, registro, hoy):
    """Crea, guarda y envía las alertas que corresponden a un registro.

    - Exceso de tiempo: alerta correctiva solo en la interfaz web.
    - Cerca de la meta: alerta preventiva en la web y por correo.
    - Meta superada: alerta correctiva en la web y por correo.
    - Si el correo falla, la alerta igual queda guardada y la pantalla
      muestra el aviso en el banner (escenario 3).
    Cada alerta se guarda en la tabla `alertas` (escenario 4).
    """
    momento = datetime.now()
    pendientes = []

    if registro["exceso_tiempo"]:
        pendientes.append((
            "exceso_tiempo",
            "correctiva",
            (
                f"{registro['nombre']} duró "
                f"{texto_minutos(registro['minutos'])} min y superó el "
                f"tiempo recomendado "
                f"({texto_minutos(registro['tiempo_recomendado'])} min). "
                f"Intenta acortarla la próxima vez."
            ),
            False,
        ))

    total = texto_numero(hoy["total_litros"])
    meta = texto_numero(hoy["meta_diaria"])

    if hoy["estado"] == "precaucion":
        pendientes.append((
            "preventiva",
            "preventiva",
            (
                f"Atención: llevas {total} L de tu meta diaria de "
                f"{meta} L ({texto_numero(hoy['porcentaje_meta'])}%). "
                f"Reduce el consumo para no superarla."
            ),
            True,
        ))
    elif hoy["estado"] == "exceso":
        pendientes.append((
            "exceso_diario",
            "correctiva",
            (
                f"Superaste tu meta diaria: llevas {total} L y tu meta "
                f"es de {meta} L."
            ),
            True,
        ))

    alertas = []

    for tipo, nivel, mensaje, por_correo in pendientes:
        alerta_id = db.insertar_alerta(
            usuario["id"], registro["id"], tipo, nivel, mensaje, momento
        )
        estado_correo, error_correo = "no_aplica", None

        if por_correo:
            enviado, error_correo = enviar_correo(
                usuario["correo"],
                "Water Controller Smart: alerta de consumo",
                mensaje,
            )
            estado_correo = "enviado" if enviado else "fallido"
            db.actualizar_correo_alerta(
                alerta_id, estado_correo, error_correo
            )

        alertas.append({
            "id": alerta_id,
            "tipo": tipo,
            "nivel": nivel,
            "mensaje": mensaje,
            "correo_estado": estado_correo,
            "correo_error": error_correo,
        })

    return alertas


def respuesta_de_registro(usuario, datos, registro):
    """Arma la respuesta común de registrar (manual o con cronómetro)."""
    hoy = resumen_del_dia(datos, registro["fecha"])
    hoy["meta_diaria"] = meta_diaria_de(datos)
    hoy["porcentaje_meta"] = round(
        hoy["total_litros"] / hoy["meta_diaria"] * 100, 1
    )

    return {
        "ok": True,
        "registro": registro,
        "hoy": hoy,
        "alertas": generar_alertas(usuario, registro, hoy),
    }


# ---------- US-005, US-006 y US-008: Historial ----------

def fecha_valida(texto):
    try:
        datetime.strptime(texto, "%Y-%m-%d")
    except (ValueError, TypeError):
        return False
    return True


def accion_historial(datos, params):
    vista = params.get("vista", "7dias")
    desde = params.get("desde")
    hasta = params.get("hasta")
    actividades = datos.get("actividades", [])
    hoy = datetime.now()

    if vista == "hoy":
        fecha_fin = hoy.strftime("%Y-%m-%d")
        fecha_ini = fecha_fin
    elif vista == "7dias":
        fecha_fin = hoy.strftime("%Y-%m-%d")
        fecha_ini = (hoy - timedelta(days=6)).strftime("%Y-%m-%d")
    elif vista == "30dias":
        fecha_fin = hoy.strftime("%Y-%m-%d")
        fecha_ini = (hoy - timedelta(days=29)).strftime("%Y-%m-%d")
    elif (
        vista == "personalizado"
        and fecha_valida(desde)
        and fecha_valida(hasta)
    ):
        # Se añadió la revisión de las fechas para que un rango mal
        # escrito no rompa la consulta.
        fecha_ini, fecha_fin = desde, hasta
    else:
        if actividades:
            fechas = sorted(a["fecha"] for a in actividades)
            fecha_ini, fecha_fin = fechas[0], fechas[-1]
        else:
            fecha_fin = hoy.strftime("%Y-%m-%d")
            fecha_ini = (hoy - timedelta(days=6)).strftime("%Y-%m-%d")

    if fecha_ini > fecha_fin:
        fecha_ini, fecha_fin = fecha_fin, fecha_ini

    filtradas = [
        a for a in actividades
        if fecha_ini <= a["fecha"] <= fecha_fin
    ]

    d_ini = datetime.strptime(fecha_ini, "%Y-%m-%d")
    d_fin = datetime.strptime(fecha_fin, "%Y-%m-%d")
    dias_totales = (d_fin - d_ini).days + 1

    por_fecha = {}
    dias_lista = []
    actual = d_ini

    while actual <= d_fin:
        fecha = actual.strftime("%Y-%m-%d")
        dias_lista.append(fecha)
        por_fecha[fecha] = 0.0
        actual += timedelta(days=1)

    for actividad in filtradas:
        fecha = actividad["fecha"]
        if fecha in por_fecha:
            por_fecha[fecha] = round(
                por_fecha[fecha] + actividad["litros"], 2
            )

    grafico_fechas = {
        "etiquetas": [
            fecha[5:].replace("-", "/") for fecha in dias_lista
        ],
        "valores": [por_fecha[fecha] for fecha in dias_lista],
    }

    total_litros = round(
        sum(a["litros"] for a in filtradas), 2
    )
    total_ahorro = round(
        sum(a.get("ahorro_litros", 0.0) for a in filtradas), 2
    )
    promedio_diario = round(
        total_litros / max(dias_totales, 1), 2
    )

    limite_diario = meta_diaria_de(datos)
    dias_cumplidos = sum(
        1 for fecha in dias_lista
        if por_fecha[fecha] <= limite_diario
    )
    porcentaje_cumplimiento = round(
        dias_cumplidos / max(dias_totales, 1) * 100
    )

    d_ini_prev = d_ini - timedelta(days=dias_totales)
    d_fin_prev = d_ini - timedelta(days=1)
    f_ini_prev = d_ini_prev.strftime("%Y-%m-%d")
    f_fin_prev = d_fin_prev.strftime("%Y-%m-%d")

    filtradas_prev = [
        a for a in actividades
        if f_ini_prev <= a["fecha"] <= f_fin_prev
    ]
    total_litros_prev = round(
        sum(a["litros"] for a in filtradas_prev), 2
    )

    if total_litros_prev > 0:
        variacion = round(
            (total_litros - total_litros_prev)
            / total_litros_prev * 100,
            1,
        )
    else:
        variacion = 0.0

    por_actividad = {}

    for actividad in filtradas:
        nombre = actividad["nombre"]

        if nombre not in por_actividad:
            por_actividad[nombre] = {
                "litros": 0.0,
                "minutos": 0.0,
                "ahorro": 0.0,
                "cantidad": 0,
            }

        item = por_actividad[nombre]
        item["litros"] = round(
            item["litros"] + actividad["litros"], 2
        )
        item["minutos"] = round(
            item["minutos"] + actividad["minutos"], 2
        )
        item["ahorro"] = round(
            item["ahorro"] + actividad.get("ahorro_litros", 0.0),
            2,
        )
        item["cantidad"] += 1

    return {
        "ok": True,
        "vista": vista,
        "fecha_ini": fecha_ini,
        "fecha_fin": fecha_fin,
        "dias_totales": dias_totales,
        "total_litros": total_litros,
        "total_ahorro": total_ahorro,
        "promedio_diario": promedio_diario,
        "num_registros": len(filtradas),
        "cumplimiento_metas": {
            "limite_diario": limite_diario,
            "dias_cumplidos": dias_cumplidos,
            "porcentaje": porcentaje_cumplimiento,
        },
        "comparativa": {
            "total_previo": total_litros_prev,
            "variacion_porcentual": variacion,
            "periodo_previo": f"{f_ini_prev} a {f_fin_prev}",
        },
        "grafico_fechas": grafico_fechas,
        "por_actividad": por_actividad,
        "actividades": list(reversed(filtradas)),
    }


# ---------- Acciones de la API ----------
# Se cambió la firma: cada acción recibe ahora el usuario que inició
# sesión (g.usuario) para leer y guardar solo sus propios datos.

def accion_iniciar_cronometro(usuario, cuerpo):
    datos = db.cargar_datos(usuario["id"])

    error = validar_actividad(datos, cuerpo.get("actividad"))
    if error:
        return {"ok": False, "error": error}

    if datos.get("cronometro"):
        en_curso = base_de(
            datos, datos["cronometro"]["actividad"]
        )["nombre"]
        return {
            "ok": False,
            "error": (
                f"Ya hay un cronómetro en marcha ({en_curso}). "
                "Deténlo primero."
            ),
        }

    # Si dos peticiones llegan a la vez, la llave primaria de la tabla
    # impide tener dos cronómetros y esta función devuelve False.
    if not db.iniciar_cronometro(
        usuario["id"], cuerpo["actividad"], time.time()
    ):
        return {
            "ok": False,
            "error": "Ya hay un cronómetro en marcha. Deténlo primero.",
        }

    return {"ok": True}


def accion_detener_cronometro(usuario, _cuerpo):
    datos = db.cargar_datos(usuario["id"])
    en_curso = datos.get("cronometro")

    if not en_curso or not db.borrar_cronometro(
        usuario["id"], confirmar=False
    ):
        return {
            "ok": False,
            "error": "No hay ningún cronómetro en marcha.",
        }

    minutos, error = validar_duracion(
        (time.time() - en_curso["inicio"]) / 60
    )

    if error:
        db.obtener_bd().commit()
        return {"ok": False, "error": error}

    registro = crear_registro(
        usuario["id"],
        datos,
        en_curso["actividad"],
        minutos,
        "cronometro",
        datetime.fromtimestamp(en_curso["inicio"]),
    )

    return respuesta_de_registro(usuario, datos, registro)


def accion_registrar_manual(usuario, cuerpo):
    datos = db.cargar_datos(usuario["id"])

    error = validar_actividad(datos, cuerpo.get("actividad"))
    if error:
        return {"ok": False, "error": error}

    minutos, error = validar_duracion(cuerpo.get("minutos"))
    if error:
        return {"ok": False, "error": error}

    registro = crear_registro(
        usuario["id"],
        datos,
        cuerpo["actividad"],
        minutos,
        "manual",
        datetime.now(),
    )

    return respuesta_de_registro(usuario, datos, registro)


def accion_guardar_caudal(usuario, cuerpo):
    actividad = cuerpo.get("actividad")
    datos = db.cargar_datos(usuario["id"])
    error = validar_actividad(datos, actividad)
    if error:
        return {"ok": False, "error": error}

    caudal = a_numero(cuerpo.get("caudal"))
    if caudal is None or caudal <= 0:
        return {
            "ok": False,
            "error": (
                "El caudal debe ser un número mayor que cero "
                "(litros por minuto)."
            ),
        }

    caudal = round(caudal, 2)

    if es_propia(actividad):
        if caudal > MAX_CAUDAL:
            return {"ok": False, "error": f"El caudal no puede superar {MAX_CAUDAL} L/min."}
        db.actualizar_campo_personalizada(
            usuario["id"], actividad, "caudal", caudal
        )
        return {"ok": True}

    # Si el valor es igual al estándar se borra la personalización.
    if caudal == CATALOGO[actividad]["caudal"]:
        db.guardar_personalizacion(
            usuario["id"], actividad, "caudal", None
        )
    else:
        db.guardar_personalizacion(
            usuario["id"], actividad, "caudal", caudal
        )

    return {"ok": True}


def accion_guardar_tiempo_recomendado(usuario, cuerpo):
    actividad = cuerpo.get("actividad")
    datos = db.cargar_datos(usuario["id"])
    error = validar_actividad(datos, actividad)
    if error:
        return {"ok": False, "error": error}

    tiempo = a_numero(cuerpo.get("tiempo_recomendado"))
    if tiempo is None or tiempo <= 0 or tiempo > MAX_MINUTOS:
        return {
            "ok": False,
            "error": (
                "El tiempo recomendado debe ser mayor que cero "
                "y no superar 1440 minutos."
            ),
        }

    tiempo = round(tiempo, 2)

    if es_propia(actividad):
        db.actualizar_campo_personalizada(
            usuario["id"], actividad, "tiempo_recomendado", tiempo
        )
        return {"ok": True}

    if tiempo == CATALOGO[actividad]["tiempo_recomendado"]:
        db.guardar_personalizacion(
            usuario["id"], actividad, "tiempo_recomendado", None
        )
    else:
        db.guardar_personalizacion(
            usuario["id"], actividad, "tiempo_recomendado", tiempo
        )

    return {"ok": True}


def accion_guardar_meta_diaria(usuario, cuerpo):
    meta = a_numero(cuerpo.get("meta_diaria"))

    if meta is None or meta <= 0:
        return {
            "ok": False,
            "error": (
                "La meta diaria debe ser un número mayor que cero "
                "(litros)."
            ),
        }

    meta = round(meta, 2)
    db.guardar_meta_diaria(usuario["id"], meta)

    return {"ok": True, "meta_diaria": meta}


def accion_guardar_porcentaje_aviso(usuario, cuerpo):
    """Se implementó el % de aviso que usa US-003 para la precaución."""
    porcentaje = a_numero(cuerpo.get("porcentaje_aviso"))

    if porcentaje is None or not 1 <= porcentaje <= 100:
        return {
            "ok": False,
            "error": "El porcentaje de aviso debe estar entre 1 y 100.",
        }

    db.guardar_porcentaje_aviso(usuario["id"], round(porcentaje))

    return {"ok": True, "porcentaje_aviso": round(porcentaje)}

def accion_crear_actividad(usuario, cuerpo):
    nombre = " ".join(str(cuerpo.get("nombre", "")).split())

    if not 1 <= len(nombre) <= MAX_NOMBRE:
        return {
            "ok": False,
            "error": f"El nombre debe tener entre 1 y {MAX_NOMBRE} caracteres.",
        }

    nombres_estandar = {i["nombre"].lower() for i in CATALOGO.values()}
    if nombre.lower() in nombres_estandar:
        return {
            "ok": False,
            "error": "Ese nombre ya existe entre las actividades estándar.",
        }

    caudal = a_numero(cuerpo.get("caudal"))
    if caudal is None or not 0 < caudal <= MAX_CAUDAL:
        return {
            "ok": False,
            "error": f"El caudal debe ser mayor que cero y máximo {MAX_CAUDAL} L/min.",
        }

    tiempo = a_numero(cuerpo.get("tiempo_recomendado"))
    if tiempo is None or not 0 < tiempo <= MAX_MINUTOS:
        return {
            "ok": False,
            "error": "El tiempo recomendado debe ser mayor que cero y no superar 1440 minutos.",
        }

    if db.contar_actividades_personalizadas(usuario["id"]) >= MAX_PERSONALIZADAS:
        return {
            "ok": False,
            "error": f"Solo puedes tener {MAX_PERSONALIZADAS} actividades propias.",
        }

    actividad_id = "p_" + secrets.token_hex(4)

    if not db.crear_actividad_personalizada(
        usuario["id"], actividad_id, nombre,
        round(caudal, 2), round(tiempo, 2),
    ):
        return {"ok": False, "error": "Ya tienes una actividad con ese nombre."}

    return {"ok": True, "id": actividad_id}


def accion_eliminar_actividad(usuario, cuerpo):
    actividad = cuerpo.get("actividad")
    datos = db.cargar_datos(usuario["id"])

    propia = (
        datos["personalizadas"].get(actividad)
        if isinstance(actividad, str) else None
    )
    if not propia or not propia["activa"]:
        return {"ok": False, "error": "Esa actividad no existe."}

    en_curso = datos.get("cronometro")
    if en_curso and en_curso["actividad"] == actividad:
        return {
            "ok": False,
            "error": "Detén el cronómetro de esa actividad antes de eliminarla.",
        }

    db.desactivar_actividad_personalizada(usuario["id"], actividad)
    return {"ok": True}


# ---------- Inicio de sesión ----------

def login_requerido(vista):
    """Se creó este decorador para proteger páginas y API.

    Sin sesión, las páginas redirigen al login y la API responde 401.
    También se comprueba que el usuario todavía exista en la base.
    """
    @functools.wraps(vista)
    def envoltura(*args, **kwargs):
        usuario = None

        if "usuario_id" in session:
            usuario = db.buscar_usuario(session["usuario_id"])

        if usuario is None:
            session.clear()
            if request.path.startswith("/api/"):
                return jsonify({
                    "ok": False,
                    "error": "Tu sesión expiró. Inicia sesión de nuevo.",
                }), 401
            return redirect(url_for("login"))

        g.usuario = usuario
        return vista(*args, **kwargs)

    return envoltura


@app.route("/", methods=["GET", "POST"])
def login():
    if "usuario_id" in session:
        return redirect(url_for("panel"))

    error = None
    correo = ""

    if request.method == "POST":
        correo = request.form.get("correo", "").strip().lower()
        contrasena = request.form.get("contrasena", "")
        usuario = db.buscar_usuario_por_correo(correo)

        # El mensaje es el mismo si falla el correo o la contraseña, para
        # no revelar qué correos están registrados.
        if usuario and check_password_hash(
            usuario["contrasena_hash"], contrasena
        ):
            session.clear()
            session["usuario_id"] = usuario["id"]
            return redirect(url_for("panel"))

        error = "Correo o contraseña incorrectos."

    return render_template("login.html", error=error, correo=correo)


@app.route("/registro", methods=["GET", "POST"])
def registro():
    if "usuario_id" in session:
        return redirect(url_for("panel"))

    error = None
    correo = ""

    if request.method == "POST":
        correo = request.form.get("correo", "").strip().lower()
        contrasena = request.form.get("contrasena", "")
        repetida = request.form.get("repetida", "")

        if not PATRON_CORREO.match(correo) or len(correo) > 120:
            error = "Escribe un correo electrónico válido."
        elif len(contrasena) < MIN_CONTRASENA:
            error = (
                f"La contraseña debe tener al menos {MIN_CONTRASENA} "
                "caracteres."
            )
        elif contrasena != repetida:
            error = "Las contraseñas no coinciden."
        else:
            # Solo se guarda el hash de la contraseña, nunca el texto.
            usuario_id = db.crear_usuario(
                correo, generate_password_hash(contrasena)
            )
            if usuario_id is None:
                error = "Ese correo ya está registrado."
            else:
                session.clear()
                session["usuario_id"] = usuario_id
                return redirect(url_for("panel"))

    return render_template("registro.html", error=error, correo=correo)


@app.route("/salir")
def salir():
    session.clear()
    return redirect(url_for("login"))


# ---------- Páginas ----------

def pagina(nombre):
    """Entrega una página interna con el correo del usuario en el menú."""
    return render_template(nombre, correo=g.usuario["correo"])


@app.route("/panel")
@login_requerido
def panel():
    return pagina("panel.html")


@app.route("/historial")
@login_requerido
def historial():
    return pagina("historial.html")


@app.route("/configuracion")
@login_requerido
def configuracion():
    return pagina("configuracion.html")


@app.route("/alertas")
@login_requerido
def alertas():
    return pagina("alertas.html")


# ---------- Rutas de la API ----------

@app.get("/api/estado")
@login_requerido
def api_estado():
    return jsonify(estado_completo(db.cargar_datos(g.usuario["id"])))


@app.get("/api/historial")
@login_requerido
def api_historial():
    datos = db.cargar_datos(g.usuario["id"])
    return jsonify(accion_historial(datos, request.args.to_dict()))


@app.get("/api/alertas")
@login_requerido
def api_alertas():
    return jsonify({
        "ok": True,
        "alertas": db.listar_alertas(g.usuario["id"]),
    })


def ruta_post(ruta, accion):
    """Registra una ruta POST que recibe JSON y responde JSON."""
    @login_requerido
    def vista():
        cuerpo = request.get_json(silent=True)
        if not isinstance(cuerpo, dict):
            cuerpo = {}
        return jsonify(accion(g.usuario, cuerpo))

    vista.__name__ = "api_" + accion.__name__
    app.add_url_rule(ruta, view_func=vista, methods=["POST"])


RUTAS_POST = {
    "/api/cronometro/iniciar": accion_iniciar_cronometro,
    "/api/cronometro/detener": accion_detener_cronometro,
    "/api/actividad": accion_registrar_manual,
    "/api/caudal": accion_guardar_caudal,
    "/api/tiempo-recomendado": accion_guardar_tiempo_recomendado,
    "/api/meta-diaria": accion_guardar_meta_diaria,
    "/api/porcentaje-aviso": accion_guardar_porcentaje_aviso,
    "/api/actividad-personalizada": accion_crear_actividad,
    "/api/actividad-personalizada/eliminar": accion_eliminar_actividad,
}

for _ruta, _accion in RUTAS_POST.items():
    ruta_post(_ruta, _accion)


@app.after_request
def sin_cache(respuesta):
    # Igual que el servidor anterior: la API nunca se guarda en caché.
    if request.path.startswith("/api/"):
        respuesta.headers["Cache-Control"] = "no-store"
    return respuesta


def main():
    direccion = f"http://localhost:{PUERTO}"
    print(
        f"Water Controller Smart funcionando en {direccion} "
        "(Ctrl + C para apagar)"
    )
    threading.Timer(1.0, webbrowser.open, [direccion]).start()
    app.run(host="127.0.0.1", port=PUERTO, debug=False)


if __name__ == "__main__":
    main()