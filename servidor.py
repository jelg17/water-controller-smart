"""Servidor de Water Controller Smart (solo usa librerías que ya vienen con Python).

Python es quien hace TODA la lógica de las historias de usuario:

  US-001  Registrar actividades (ducha, lavado de platos, riego, aseo)
          - con cronómetro (iniciar / detener, también desde el panel con un clic)
          - o escribiendo los minutos a mano
          - rechaza duraciones vacías, negativas o iguales a cero
  US-002  Calcular los litros de cada actividad
          - litros = minutos x caudal (L/min) de la actividad
          - usa el caudal personalizado si el usuario lo cambió
          - arma el mensaje: litros gastados y litros que se ahorrarían
          - suma el consumo acumulado del día

Los datos se guardan en el archivo datos.json (junto a este archivo).
También sigue funcionando la validación de facturas (/api/factura).

Uso:
    python servidor.py
Para apagarlo: Ctrl + C
"""
import functools
import json
import math
import os
import re
import threading
import time
import webbrowser
from datetime import datetime
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer

PUERTO = 8000
CARPETA = os.path.dirname(os.path.abspath(__file__))   # la carpeta donde está este archivo
ARCHIVO_DATOS = os.path.join(CARPETA, "datos.json")
CANDADO = threading.Lock()                              # evita que dos peticiones escriban a la vez

MAX_MINUTOS = 1440                                      # una actividad no puede durar más de 24 horas

# ---------- Catálogo de actividades ----------
# caudal = litros por minuto estándar · tiempo_recomendado = minutos máximos recomendados.
# Son valores de referencia: el usuario puede personalizar el caudal (US-002, escenario 2).
CATALOGO = {
    "ducha":  {"nombre": "Ducha",            "caudal": 9.0,  "tiempo_recomendado": 5},
    "platos": {"nombre": "Lavado de platos", "caudal": 6.0,  "tiempo_recomendado": 10},
    "riego":  {"nombre": "Riego",            "caudal": 12.0, "tiempo_recomendado": 15},
    "aseo":   {"nombre": "Aseo",             "caudal": 8.0,  "tiempo_recomendado": 10},
}

ERROR_DURACION = "La duración no es válida: escribe un número de minutos mayor que cero."


# ---------- Utilidades ----------

def a_numero(texto):
    """Convierte lo que escribió el usuario en número (acepta 12,5 y 12.5). None si no sirve."""
    try:
        numero = float(str(texto).strip().replace(",", "."))
    except ValueError:
        return None
    return numero if math.isfinite(numero) else None   # descarta "nan" e "inf"


def texto_numero(valor, decimales=1):
    """12.5 -> '12,5'   ·   4.0 -> '4,0'   (formato con coma, como en español)."""
    return f"{valor:.{decimales}f}".replace(".", ",")


def texto_minutos(minutos):
    """4.0 -> '4'   ·   2.5 -> '2,5'   ·   0.33 -> '0,33'"""
    return f"{round(minutos, 2):g}".replace(".", ",")


# ---------- Datos guardados (datos.json) ----------

def datos_vacios():
    return {"actividades": [], "caudales": {}, "cronometro": None, "siguiente_id": 1}


def cargar_datos():
    try:
        with open(ARCHIVO_DATOS, encoding="utf-8") as archivo:
            datos = json.load(archivo)
    except (OSError, ValueError):                        # no existe todavía o está dañado
        return datos_vacios()
    return {**datos_vacios(), **datos}


def guardar_datos(datos):
    temporal = ARCHIVO_DATOS + ".tmp"                    # se escribe aparte y luego se reemplaza (no queda a medias)
    with open(temporal, "w", encoding="utf-8") as archivo:
        json.dump(datos, archivo, ensure_ascii=False, indent=2)
    os.replace(temporal, ARCHIVO_DATOS)


# ---------- US-001: validación de la duración ----------

def validar_duracion(texto):
    """Devuelve (minutos, None) o (None, "mensaje de error").
    Rechaza vacío, texto, negativos y cero."""
    minutos = a_numero(texto)
    if minutos is not None:
        minutos = round(minutos, 2)                      # se redondea ANTES de revisar (0,001 min quedaría en 0)
    if minutos is None or minutos <= 0 or minutos > MAX_MINUTOS:
        return None, ERROR_DURACION
    return minutos, None


def validar_actividad(actividad):
    if actividad not in CATALOGO:
        return "Elige una actividad válida (ducha, lavado de platos, riego o aseo)."
    return None


# ---------- US-002: caudal y cálculo de litros ----------

def caudal_de(datos, actividad):
    """Caudal que se usa para la actividad: el personalizado si existe, si no el estándar."""
    personalizado = datos["caudales"].get(actividad)
    if personalizado is not None:
        return personalizado, True
    return CATALOGO[actividad]["caudal"], False


def calcular_litros(minutos, caudal):
    """litros = minutos x caudal (L/min)"""
    return round(minutos * caudal, 2)


def calcular_ahorro(minutos, caudal, tiempo_recomendado):
    """Litros que se ahorrarían si la actividad hubiera durado solo el tiempo recomendado."""
    return round(max(0.0, minutos - tiempo_recomendado) * caudal, 2)


def armar_mensaje(registro):
    """Mensaje comprensible: litros gastados y litros que se ahorrarían (US-002, escenario 3)."""
    recomendado = registro["tiempo_recomendado"]
    mensaje = (f"{registro['nombre']}: gastaste {texto_numero(registro['litros'])} L "
               f"({texto_minutos(registro['minutos'])} min a {texto_numero(registro['caudal'])} L/min).")
    if registro["ahorro_litros"] > 0:
        mensaje += (f" Si hubiera durado el tiempo recomendado ({texto_minutos(recomendado)} min) "
                    f"te habrías ahorrado {texto_numero(registro['ahorro_litros'])} L.")
    else:
        mensaje += f" Estás dentro del tiempo recomendado ({texto_minutos(recomendado)} min)."
    return mensaje


def crear_registro(datos, actividad, minutos, origen, momento):
    """Crea el registro de una actividad ya validada, calcula sus litros y lo agrega a los datos."""
    caudal, personalizado = caudal_de(datos, actividad)
    recomendado = CATALOGO[actividad]["tiempo_recomendado"]
    registro = {
        "id": datos["siguiente_id"],
        "actividad": actividad,
        "nombre": CATALOGO[actividad]["nombre"],
        "fecha": momento.strftime("%Y-%m-%d"),
        "hora": momento.strftime("%H:%M:%S"),
        "minutos": minutos,
        "caudal": caudal,                                # se guarda el caudal usado en ese momento
        "caudal_personalizado": personalizado,
        "litros": calcular_litros(minutos, caudal),
        "tiempo_recomendado": recomendado,
        "ahorro_litros": calcular_ahorro(minutos, caudal, recomendado),
        "origen": origen,                                # "cronometro" o "manual"
    }
    registro["mensaje"] = armar_mensaje(registro)
    datos["siguiente_id"] += 1
    datos["actividades"].append(registro)
    return registro


def resumen_del_dia(datos, fecha):
    """Actividades de un día y su consumo acumulado (US-002, escenario 4)."""
    del_dia = [a for a in datos["actividades"] if a["fecha"] == fecha]
    return {
        "fecha": fecha,
        "total_litros": round(sum(a["litros"] for a in del_dia), 2),
        "cantidad": len(del_dia),
        "actividades": del_dia,
    }


def estado_completo(datos):
    """Todo lo que necesita el panel para dibujarse."""
    catalogo = []
    for clave, info in CATALOGO.items():
        caudal, personalizado = caudal_de(datos, clave)
        catalogo.append({
            "id": clave, "nombre": info["nombre"], "caudal": caudal,
            "caudal_estandar": info["caudal"], "personalizado": personalizado,
            "tiempo_recomendado": info["tiempo_recomendado"],
        })

    cronometro = None
    if datos["cronometro"]:
        cronometro = {
            "actividad": datos["cronometro"]["actividad"],
            "nombre": CATALOGO[datos["cronometro"]["actividad"]]["nombre"],
            "segundos": round(time.time() - datos["cronometro"]["inicio"], 1),
        }
    return {
        "ok": True,
        "catalogo": catalogo,
        "cronometro": cronometro,
        "hoy": resumen_del_dia(datos, datetime.now().strftime("%Y-%m-%d")),
    }


# ---------- Acciones (cada una la llama una ruta de la API) ----------

def accion_iniciar_cronometro(cuerpo):
    error = validar_actividad(cuerpo.get("actividad"))
    if error:
        return {"ok": False, "error": error}
    with CANDADO:
        datos = cargar_datos()
        if datos["cronometro"]:
            en_curso = CATALOGO[datos["cronometro"]["actividad"]]["nombre"]
            return {"ok": False, "error": f"Ya hay un cronómetro en marcha ({en_curso}). Deténlo primero."}
        datos["cronometro"] = {"actividad": cuerpo["actividad"], "inicio": time.time()}
        guardar_datos(datos)
    return {"ok": True}


def accion_detener_cronometro(_cuerpo):
    with CANDADO:
        datos = cargar_datos()
        en_curso = datos["cronometro"]
        if not en_curso:
            return {"ok": False, "error": "No hay ningún cronómetro en marcha."}
        datos["cronometro"] = None                       # el cronómetro se apaga pase lo que pase

        minutos, error = validar_duracion((time.time() - en_curso["inicio"]) / 60)
        if error:                                        # por ejemplo, se detuvo al instante
            guardar_datos(datos)
            return {"ok": False, "error": error}

        registro = crear_registro(datos, en_curso["actividad"], minutos, "cronometro",
                                  datetime.fromtimestamp(en_curso["inicio"]))
        guardar_datos(datos)
        return {"ok": True, "registro": registro, "hoy": resumen_del_dia(datos, registro["fecha"])}


def accion_registrar_manual(cuerpo):
    error = validar_actividad(cuerpo.get("actividad"))
    if error:
        return {"ok": False, "error": error}
    minutos, error = validar_duracion(cuerpo.get("minutos"))
    if error:
        return {"ok": False, "error": error}
    with CANDADO:
        datos = cargar_datos()
        registro = crear_registro(datos, cuerpo["actividad"], minutos, "manual", datetime.now())
        guardar_datos(datos)
        return {"ok": True, "registro": registro, "hoy": resumen_del_dia(datos, registro["fecha"])}


def accion_guardar_caudal(cuerpo):
    """Caudal personalizado de una actividad. Debe ser un número mayor que cero."""
    error = validar_actividad(cuerpo.get("actividad"))
    if error:
        return {"ok": False, "error": error}
    caudal = a_numero(cuerpo.get("caudal"))
    if caudal is None or caudal <= 0:
        return {"ok": False, "error": "El caudal debe ser un número mayor que cero (litros por minuto)."}
    caudal = round(caudal, 2)
    with CANDADO:
        datos = cargar_datos()
        if caudal == CATALOGO[cuerpo["actividad"]]["caudal"]:
            datos["caudales"].pop(cuerpo["actividad"], None)      # igual al estándar: no cuenta como personalizado
        else:
            datos["caudales"][cuerpo["actividad"]] = caudal
        guardar_datos(datos)
    return {"ok": True}


# ---------- Validación de la factura (ya existía) ----------

def validar_factura(datos):
    """Revisa los datos del formulario. Devuelve (factura, None) o (None, "mensaje de error")."""
    mes = str(datos.get("mes", ""))
    if not re.fullmatch(r"\d{4}-(0[1-9]|1[0-2])", mes):          # formato AAAA-MM, ejemplo 2026-08
        return None, "Elige el mes de la factura."

    consumo = a_numero(datos.get("consumo"))
    if consumo is None or consumo < 0:
        return None, "El consumo debe ser un número igual o mayor que cero."

    total = a_numero(datos.get("total"))
    if total is None or total < 0:
        return None, "El total a pagar debe ser un número igual o mayor que cero."

    return {"mes": mes, "consumo_m3": consumo, "total": total}, None


def accion_factura(cuerpo):
    factura, error = validar_factura(cuerpo)
    return {"ok": False, "error": error} if error else {"ok": True, "factura": factura}


# ---------- Servidor ----------

RUTAS_POST = {
    "/api/cronometro/iniciar": accion_iniciar_cronometro,
    "/api/cronometro/detener": accion_detener_cronometro,
    "/api/actividad": accion_registrar_manual,
    "/api/caudal": accion_guardar_caudal,
    "/api/factura": accion_factura,
}


class Manejador(SimpleHTTPRequestHandler):
    """SimpleHTTPRequestHandler ya sabe entregar los archivos de la carpeta (html, css, js).
    Solo le agregamos las rutas de la API."""

    def do_GET(self):
        ruta = self.path.split("?")[0]
        if ruta == "/api/estado":
            with CANDADO:
                self.responder_json(estado_completo(cargar_datos()))
        elif ruta.startswith("/datos.json"):             # los datos se piden por la API, no como archivo
            self.send_error(404)
        else:
            super().do_GET()

    def do_POST(self):
        accion = RUTAS_POST.get(self.path.split("?")[0])
        if accion is None:
            self.send_error(404)
            return

        largo = int(self.headers.get("Content-Length", 0))
        if largo > 10_000:                               # estos datos pesan muy poco; más que esto no es normal
            self.send_error(413)
            return
        try:
            cuerpo = json.loads(self.rfile.read(largo) or b"{}")
        except ValueError:                               # no era un JSON válido
            cuerpo = {}
        if not isinstance(cuerpo, dict):
            cuerpo = {}

        self.responder_json(accion(cuerpo))

    def responder_json(self, contenido):
        cuerpo = json.dumps(contenido).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(cuerpo)))
        self.end_headers()
        self.wfile.write(cuerpo)


def main():
    # `directory=CARPETA` hace que sirva los archivos del proyecto sin importar desde dónde se ejecute
    manejador = functools.partial(Manejador, directory=CARPETA)
    servidor = ThreadingHTTPServer(("127.0.0.1", PUERTO), manejador)

    direccion = f"http://localhost:{PUERTO}"
    print(f"Water Controller Smart funcionando en {direccion}  (Ctrl + C para apagar)")
    webbrowser.open(direccion)                           # abre el navegador solo

    try:
        servidor.serve_forever()
    except KeyboardInterrupt:
        print("\nServidor apagado.")


if __name__ == "__main__":
    main()