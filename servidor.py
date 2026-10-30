"""Servidor de Water Controller Smart.

US-001: Registrar actividades.
US-002: Calcular consumo de agua.
US-005: Consultar historial y estadísticas.
US-006: Reportes de ahorro y comparativas.
US-007: Personalizar caudal y tiempo recomendado.
US-008: Configurar la meta diaria de consumo.
"""
import functools
import json
import math
import os
import re
import threading
import time
import webbrowser
from datetime import datetime, timedelta
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs

PUERTO = 7500
CARPETA = os.path.dirname(os.path.abspath(__file__))
ARCHIVO_DATOS = os.path.join(CARPETA, "datos.json")
CANDADO = threading.Lock()

MAX_MINUTOS = 1440
META_DIARIA_PREDETERMINADA = 100.0
PORCENTAJE_AVISO_META = 80

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


def datos_vacios():
    return {
        "actividades": [],
        "caudales": {},
        "tiempos_recomendados": {},
        "meta_diaria": META_DIARIA_PREDETERMINADA,
        "cronometro": None,
        "siguiente_id": 1,
    }


def cargar_datos():
    try:
        with open(ARCHIVO_DATOS, encoding="utf-8") as archivo:
            datos = json.load(archivo)
    except (OSError, ValueError):
        return datos_vacios()

    # Incorpora las claves nuevas sin eliminar los datos anteriores.
    datos = {**datos_vacios(), **datos}

    for clave in ("caudales", "tiempos_recomendados"):
        if not isinstance(datos.get(clave), dict):
            datos[clave] = {}

    if not isinstance(datos.get("actividades"), list):
        datos["actividades"] = []

    return datos


def guardar_datos(datos):
    temporal = ARCHIVO_DATOS + ".tmp"
    with open(temporal, "w", encoding="utf-8") as archivo:
        json.dump(datos, archivo, ensure_ascii=False, indent=2)
    os.replace(temporal, ARCHIVO_DATOS)


def validar_duracion(texto):
    minutos = a_numero(texto)
    if minutos is not None:
        minutos = round(minutos, 2)

    if minutos is None or minutos <= 0 or minutos > MAX_MINUTOS:
        return None, ERROR_DURACION

    return minutos, None


def validar_actividad(actividad):
    if actividad not in CATALOGO:
        return (
            "Elige una actividad válida "
            "(ducha, lavado de platos, riego o aseo)."
        )
    return None


def caudal_de(datos, actividad):
    personalizado = datos.get("caudales", {}).get(actividad)

    if personalizado is not None:
        return personalizado, True

    return CATALOGO[actividad]["caudal"], False


def tiempo_recomendado_de(datos, actividad):
    personalizado = datos.get("tiempos_recomendados", {}).get(actividad)

    if personalizado is not None:
        return personalizado, True

    return CATALOGO[actividad]["tiempo_recomendado"], False


def meta_diaria_de(datos):
    meta = a_numero(datos.get("meta_diaria"))

    if meta is None or meta <= 0:
        return META_DIARIA_PREDETERMINADA

    return meta


def calcular_litros(minutos, caudal):
    return round(minutos * caudal, 2)


def calcular_ahorro(minutos, caudal, tiempo_recomendado):
    return round(max(0.0, minutos - tiempo_recomendado) * caudal, 2)


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


def crear_registro(datos, actividad, minutos, origen, momento):
    caudal, caudal_personalizado = caudal_de(datos, actividad)
    recomendado, _ = tiempo_recomendado_de(datos, actividad)

    registro = {
        "id": datos["siguiente_id"],
        "actividad": actividad,
        "nombre": CATALOGO[actividad]["nombre"],
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
    }

    registro["mensaje"] = armar_mensaje(registro)
    datos["siguiente_id"] += 1
    datos["actividades"].append(registro)

    return registro


def resumen_del_dia(datos, fecha):
    del_dia = [
        actividad
        for actividad in datos["actividades"]
        if actividad["fecha"] == fecha
    ]

    return {
        "fecha": fecha,
        "total_litros": round(
            sum(a["litros"] for a in del_dia), 2
        ),
        "cantidad": len(del_dia),
        "actividades": del_dia,
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
        })

    cronometro = None

    if datos.get("cronometro"):
        actividad = datos["cronometro"]["actividad"]
        cronometro = {
            "actividad": actividad,
            "nombre": CATALOGO[actividad]["nombre"],
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
    hoy["meta_superada"] = hoy["total_litros"] >= meta
    hoy["meta_cercana"] = (
        hoy["total_litros"] >= meta * PORCENTAJE_AVISO_META / 100
        and hoy["total_litros"] < meta
    )

    return {
        "ok": True,
        "catalogo": catalogo,
        "cronometro": cronometro,
        "meta_diaria": meta,
        "hoy": hoy,
    }


# ---------- US-005, US-006 y US-008: Historial ----------

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
    elif vista == "personalizado" and desde and hasta:
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

def accion_iniciar_cronometro(cuerpo):
    error = validar_actividad(cuerpo.get("actividad"))
    if error:
        return {"ok": False, "error": error}

    with CANDADO:
        datos = cargar_datos()

        if datos.get("cronometro"):
            en_curso = CATALOGO[
                datos["cronometro"]["actividad"]
            ]["nombre"]
            return {
                "ok": False,
                "error": (
                    f"Ya hay un cronómetro en marcha ({en_curso}). "
                    "Deténlo primero."
                ),
            }

        datos["cronometro"] = {
            "actividad": cuerpo["actividad"],
            "inicio": time.time(),
        }
        guardar_datos(datos)

    return {"ok": True}


def accion_detener_cronometro(_cuerpo):
    with CANDADO:
        datos = cargar_datos()
        en_curso = datos.get("cronometro")

        if not en_curso:
            return {
                "ok": False,
                "error": "No hay ningún cronómetro en marcha.",
            }

        datos["cronometro"] = None
        minutos, error = validar_duracion(
            (time.time() - en_curso["inicio"]) / 60
        )

        if error:
            guardar_datos(datos)
            return {"ok": False, "error": error}

        registro = crear_registro(
            datos,
            en_curso["actividad"],
            minutos,
            "cronometro",
            datetime.fromtimestamp(en_curso["inicio"]),
        )
        guardar_datos(datos)

        return {
            "ok": True,
            "registro": registro,
            "hoy": resumen_del_dia(datos, registro["fecha"]),
        }


def accion_registrar_manual(cuerpo):
    error = validar_actividad(cuerpo.get("actividad"))
    if error:
        return {"ok": False, "error": error}

    minutos, error = validar_duracion(cuerpo.get("minutos"))
    if error:
        return {"ok": False, "error": error}

    with CANDADO:
        datos = cargar_datos()
        registro = crear_registro(
            datos,
            cuerpo["actividad"],
            minutos,
            "manual",
            datetime.now(),
        )
        guardar_datos(datos)

        return {
            "ok": True,
            "registro": registro,
            "hoy": resumen_del_dia(datos, registro["fecha"]),
        }


def accion_guardar_caudal(cuerpo):
    actividad = cuerpo.get("actividad")
    error = validar_actividad(actividad)
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

    with CANDADO:
        datos = cargar_datos()

        if caudal == CATALOGO[actividad]["caudal"]:
            datos["caudales"].pop(actividad, None)
        else:
            datos["caudales"][actividad] = caudal

        guardar_datos(datos)

    return {"ok": True}


def accion_guardar_tiempo_recomendado(cuerpo):
    actividad = cuerpo.get("actividad")
    error = validar_actividad(actividad)
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

    with CANDADO:
        datos = cargar_datos()

        if tiempo == CATALOGO[actividad]["tiempo_recomendado"]:
            datos["tiempos_recomendados"].pop(actividad, None)
        else:
            datos["tiempos_recomendados"][actividad] = tiempo

        guardar_datos(datos)

    return {"ok": True}


def accion_guardar_meta_diaria(cuerpo):
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

    with CANDADO:
        datos = cargar_datos()
        datos["meta_diaria"] = meta
        guardar_datos(datos)

    return {"ok": True, "meta_diaria": meta}


def validar_factura(datos):
    mes = str(datos.get("mes", ""))

    if not re.fullmatch(r"\\d{4}-(0[1-9]|1[0-2])", mes):
        return None, "Elige el mes de la factura."

    consumo = a_numero(datos.get("consumo"))
    if consumo is None or consumo < 0:
        return None, (
            "El consumo debe ser un número igual o mayor que cero."
        )

    total = a_numero(datos.get("total"))
    if total is None or total < 0:
        return None, (
            "El total a pagar debe ser un número igual o mayor que cero."
        )

    return {
        "mes": mes,
        "consumo_m3": consumo,
        "total": total,
    }, None


def accion_factura(cuerpo):
    factura, error = validar_factura(cuerpo)
    if error:
        return {"ok": False, "error": error}
    return {"ok": True, "factura": factura}


RUTAS_POST = {
    "/api/cronometro/iniciar": accion_iniciar_cronometro,
    "/api/cronometro/detener": accion_detener_cronometro,
    "/api/actividad": accion_registrar_manual,
    "/api/caudal": accion_guardar_caudal,
    "/api/tiempo-recomendado": accion_guardar_tiempo_recomendado,
    "/api/meta-diaria": accion_guardar_meta_diaria,
    "/api/factura": accion_factura,
}


class Manejador(SimpleHTTPRequestHandler):
    def do_GET(self):
        partes = self.path.split("?", 1)
        ruta = partes[0]
        params = {}

        if len(partes) > 1:
            params = {
                clave: valores[0]
                for clave, valores in parse_qs(
                    partes[1], keep_blank_values=True
                ).items()
            }

        if ruta == "/api/estado":
            with CANDADO:
                self.responder_json(
                    estado_completo(cargar_datos())
                )
        elif ruta == "/api/historial":
            with CANDADO:
                datos = cargar_datos()
                self.responder_json(
                    accion_historial(datos, params)
                )
        elif ruta.startswith("/datos.json"):
            self.send_error(404)
        else:
            super().do_GET()

    def do_POST(self):
        ruta = self.path.split("?", 1)[0]
        accion = RUTAS_POST.get(ruta)

        if accion is None:
            self.send_error(404)
            return

        try:
            largo = int(self.headers.get("Content-Length", 0))
        except ValueError:
            self.send_error(400)
            return

        if largo > 10_000:
            self.send_error(413)
            return

        try:
            cuerpo = json.loads(self.rfile.read(largo) or b"{}")
        except (ValueError, UnicodeDecodeError):
            cuerpo = {}

        if not isinstance(cuerpo, dict):
            cuerpo = {}

        self.responder_json(accion(cuerpo))

    def responder_json(self, contenido):
        cuerpo = json.dumps(
            contenido, ensure_ascii=False
        ).encode("utf-8")

        self.send_response(200)
        self.send_header(
            "Content-Type", "application/json; charset=utf-8"
        )
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(cuerpo)))
        self.end_headers()
        self.wfile.write(cuerpo)


def main():
    manejador = functools.partial(
        Manejador, directory=CARPETA
    )
    servidor = ThreadingHTTPServer(
        ("127.0.0.1", PUERTO), manejador
    )

    direccion = f"http://localhost:{PUERTO}"
    print(
        f"Water Controller Smart funcionando en {direccion} "
        "(Ctrl + C para apagar)"
    )
    webbrowser.open(direccion)

    try:
        servidor.serve_forever()
    except KeyboardInterrupt:
        print("\\nServidor apagado.")
    finally:
        servidor.server_close()


if __name__ == "__main__":
    main()