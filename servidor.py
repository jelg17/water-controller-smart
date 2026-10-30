"""Servidor de Water Controller Smart (solo usa librerías que ya vienen con Python).

Python es quien hace TODA la lógica de las historias de usuario:
  US-001  Registrar actividades (ducha, lavado de platos, riego, aseo)
  US-002  Calcular los litros de cada actividad
  US-005  Consultar historial y estadísticas de consumo de agua (RF05)
          - Rango continuo de fechas (días con 0 L para gráficos continuos)
          - Vistas rápidas (7 días, 30 días, todo el historial)
          - Promedios por día y por actividad
  US-006  Generar reportes de ahorro y comparativas (RF06)
          - Comparativa porcentual frente al período anterior de igual duración
          - Cumplimiento de metas de consumo diario
          - Exportación de reportes de consumo en CSV

Uso:
    py servidor.py
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
from datetime import datetime, timedelta
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer

PUERTO = 7500
CARPETA = os.path.dirname(os.path.abspath(__file__))
ARCHIVO_DATOS = os.path.join(CARPETA, "datos.json")
CANDADO = threading.Lock()

MAX_MINUTOS = 1440

CATALOGO = {
    "ducha":  {"nombre": "Ducha",            "caudal": 9.0,  "tiempo_recomendado": 5},
    "platos": {"nombre": "Lavado de platos", "caudal": 6.0,  "tiempo_recomendado": 10},
    "riego":  {"nombre": "Riego",            "caudal": 12.0, "tiempo_recomendado": 15},
    "aseo":   {"nombre": "Aseo",             "caudal": 8.0,  "tiempo_recomendado": 10},
}

ERROR_DURACION = "La duración no es válida: escribe un número de minutos mayor que cero."


def a_numero(texto):
    try:
        numero = float(str(texto).strip().replace(",", "."))
    except ValueError:
        return None
    return numero if math.isfinite(numero) else None


def texto_numero(valor, decimales=1):
    return f"{valor:.{decimales}f}".replace(".", ",")


def texto_minutos(minutos):
    return f"{round(minutos, 2):g}".replace(".", ",")


def datos_vacios():
    return {"actividades": [], "caudales": {}, "cronometro": None, "siguiente_id": 1}


def cargar_datos():
    try:
        with open(ARCHIVO_DATOS, encoding="utf-8") as archivo:
            datos = json.load(archivo)
    except (OSError, ValueError):
        return datos_vacios()
    return {**datos_vacios(), **datos}


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
        return "Elige una actividad válida (ducha, lavado de platos, riego o aseo)."
    return None


def caudal_de(datos, actividad):
    personalizado = datos["caudales"].get(actividad)
    if personalizado is not None:
        return personalizado, True
    return CATALOGO[actividad]["caudal"], False


def calcular_litros(minutos, caudal):
    return round(minutos * caudal, 2)


def calcular_ahorro(minutos, caudal, tiempo_recomendado):
    return round(max(0.0, minutos - tiempo_recomendado) * caudal, 2)


def armar_mensaje(registro):
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
    caudal, personalizado = caudal_de(datos, actividad)
    recomendado = CATALOGO[actividad]["tiempo_recomendado"]
    registro = {
        "id": datos["siguiente_id"],
        "actividad": actividad,
        "nombre": CATALOGO[actividad]["nombre"],
        "fecha": momento.strftime("%Y-%m-%d"),
        "hora": momento.strftime("%H:%M:%S"),
        "minutos": minutos,
        "caudal": caudal,
        "caudal_personalizado": personalizado,
        "litros": calcular_litros(minutos, caudal),
        "tiempo_recomendado": recomendado,
        "ahorro_litros": calcular_ahorro(minutos, caudal, recomendado),
        "origen": origen,
    }
    registro["mensaje"] = armar_mensaje(registro)
    datos["siguiente_id"] += 1
    datos["actividades"].append(registro)
    return registro


def resumen_del_dia(datos, fecha):
    del_dia = [a for a in datos["actividades"] if a["fecha"] == fecha]
    return {
        "fecha": fecha,
        "total_litros": round(sum(a["litros"] for a in del_dia), 2),
        "cantidad": len(del_dia),
        "actividades": del_dia,
    }


def estado_completo(datos):
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


# ---------- US-005 & US-006: Histórico analítico con rango de fechas continuo ----------

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
        fecha_ini = desde
        fecha_fin = hasta
    else:  # "todo" o por defecto si hay datos
        if actividades:
            fechas_existentes = sorted([a["fecha"] for a in actividades])
            fecha_ini = fechas_existentes[0]
            fecha_fin = fechas_existentes[-1]
        else:
            fecha_fin = hoy.strftime("%Y-%m-%d")
            fecha_ini = (hoy - timedelta(days=6)).strftime("%Y-%m-%d")

    if fecha_ini > fecha_fin:
        fecha_ini, fecha_fin = fecha_fin, fecha_ini

    # 1. Filtrar actividades del periodo
    filtradas = [a for a in actividades if fecha_ini <= a["fecha"] <= fecha_fin]

    # 2. Rango continuo de fechas para la gráfica (US-005)
    d_ini = datetime.strptime(fecha_ini, "%Y-%m-%d")
    d_fin = datetime.strptime(fecha_fin, "%Y-%m-%d")
    dias_totales = (d_fin - d_ini).days + 1

    por_fecha = {}
    dias_lista = []
    actual = d_ini
    while actual <= d_fin:
        f_str = actual.strftime("%Y-%m-%d")
        dias_lista.append(f_str)
        por_fecha[f_str] = 0.0
        actual += timedelta(days=1)

    for a in filtradas:
        f = a["fecha"]
        if f in por_fecha:
            por_fecha[f] = round(por_fecha[f] + a["litros"], 2)

    grafico_fechas = {
        "etiquetas": [f[5:].replace("-", "/") for f in dias_lista],  # Formato MM/DD
        "valores": [por_fecha[f] for f in dias_lista]
    }

    # 3. Métricas y Totales
    total_litros = round(sum(a["litros"] for a in filtradas), 2)
    total_ahorro = round(sum(a.get("ahorro_litros", 0.0) for a in filtradas), 2)
    promedio_diario = round(total_litros / max(dias_totales, 1), 2)

    # 4. Cumplimiento de Metas (US-006): días con consumo bajo la meta diaria (100 L)
    limite_diario = 100.0
    dias_cumplidos = sum(1 for f in dias_lista if por_fecha[f] <= limite_diario)
    porcentaje_cumplimiento = round((dias_cumplidos / max(dias_totales, 1)) * 100)

    # 5. Comparativa Periódica (US-006): comparar contra el período anterior de igual duración
    d_ini_prev = d_ini - timedelta(days=dias_totales)
    d_fin_prev = d_ini - timedelta(days=1)
    f_ini_prev = d_ini_prev.strftime("%Y-%m-%d")
    f_fin_prev = d_fin_prev.strftime("%Y-%m-%d")

    filtradas_prev = [a for a in actividades if f_ini_prev <= a["fecha"] <= f_fin_prev]
    total_litros_prev = round(sum(a["litros"] for a in filtradas_prev), 2)

    if total_litros_prev > 0:
        variacion = round(((total_litros - total_litros_prev) / total_litros_prev) * 100, 1)
    else:
        variacion = 0.0

    # 6. Desglose por Actividad
    por_actividad = {}
    for a in filtradas:
        act = a["nombre"]
        if act not in por_actividad:
            por_actividad[act] = {"litros": 0.0, "minutos": 0.0, "ahorro": 0.0, "cantidad": 0}
        por_actividad[act]["litros"] = round(por_actividad[act]["litros"] + a["litros"], 2)
        por_actividad[act]["minutos"] = round(por_actividad[act]["minutos"] + a["minutos"], 2)
        por_actividad[act]["ahorro"] = round(por_actividad[act]["ahorro"] + a.get("ahorro_litros", 0.0), 2)
        por_actividad[act]["cantidad"] += 1

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
            "porcentaje": porcentaje_cumplimiento
        },
        "comparativa": {
            "total_previo": total_litros_prev,
            "variacion_porcentual": variacion,
            "periodo_previo": f"{f_ini_prev} a {f_fin_prev}"
        },
        "grafico_fechas": grafico_fechas,
        "por_actividad": por_actividad,
        "actividades": list(reversed(filtradas))
    }


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
        datos["cronometro"] = None

        minutos, error = validar_duracion((time.time() - en_curso["inicio"]) / 60)
        if error:
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
            datos["caudales"].pop(cuerpo["actividad"], None)
        else:
            datos["caudales"][cuerpo["actividad"]] = caudal
        guardar_datos(datos)
    return {"ok": True}


def validar_factura(datos):
    mes = str(datos.get("mes", ""))
    if not re.fullmatch(r"\d{4}-(0[1-9]|1[0-2])", mes):
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


RUTAS_POST = {
    "/api/cronometro/iniciar": accion_iniciar_cronometro,
    "/api/cronometro/detener": accion_detener_cronometro,
    "/api/actividad": accion_registrar_manual,
    "/api/caudal": accion_guardar_caudal,
    "/api/factura": accion_factura,
}


class Manejador(SimpleHTTPRequestHandler):
    def do_GET(self):
        partes = self.path.split("?")
        ruta = partes[0]
        params = {}
        if len(partes) > 1:
            for p in partes[1].split("&"):
                if "=" in p:
                    k, v = p.split("=", 1)
                    params[k] = v

        if ruta == "/api/estado":
            with CANDADO:
                self.responder_json(estado_completo(cargar_datos()))
        elif ruta == "/api/historial":
            with CANDADO:
                datos = cargar_datos()
                self.responder_json(accion_historial(datos, params))
        elif ruta.startswith("/datos.json"):
            self.send_error(404)
        else:
            super().do_GET()

    def do_POST(self):
        accion = RUTAS_POST.get(self.path.split("?")[0])
        if accion is None:
            self.send_error(404)
            return

        largo = int(self.headers.get("Content-Length", 0))
        if largo > 10_000:
            self.send_error(413)
            return
        try:
            cuerpo = json.loads(self.rfile.read(largo) or b"{}")
        except ValueError:
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
    manejador = functools.partial(Manejador, directory=CARPETA)
    servidor = ThreadingHTTPServer(("127.0.0.1", PUERTO), manejador)

    direccion = f"http://localhost:{PUERTO}"
    print(f"Water Controller Smart funcionando en {direccion}  (Ctrl + C para apagar)")
    webbrowser.open(direccion)

    try:
        servidor.serve_forever()
    except KeyboardInterrupt:
        print("\nServidor apagado.")


if __name__ == "__main__":
    main()