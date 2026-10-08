"""Servidor de Water Controller Smart (solo usa librerías que ya vienen con Python).

Hace dos cosas:
  1. Muestra las páginas del proyecto en http://localhost:8000
  2. Recibe los datos de la factura que el usuario escribe en la página
     "Agregar factura", los REVISA y le responde a la página si están bien.

Python solo valida; quien guarda la factura es el navegador (localStorage).

Uso:
    python servidor.py
Para apagarlo: Ctrl + C
"""
import functools
import json
import math
import os
import re
import webbrowser
from http.server import HTTPServer, SimpleHTTPRequestHandler

PUERTO = 7500
CARPETA = os.path.dirname(os.path.abspath(__file__))   # la carpeta donde está este archivo


# ---------- Validación de la factura ----------

def a_numero(texto):
    """Convierte lo que escribió el usuario en número (acepta 12,5 y 12.5). None si no sirve."""
    try:
        numero = float(str(texto).strip().replace(",", "."))
    except ValueError:
        return None
    return numero if math.isfinite(numero) else None   # descarta "nan" e "inf"


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


# ---------- Servidor ----------

class Manejador(SimpleHTTPRequestHandler):
    """SimpleHTTPRequestHandler ya sabe entregar los archivos de la carpeta (html, css, js).
    Solo le agregamos qué hacer cuando la página nos envía una factura (POST)."""

    def do_POST(self):
        if self.path != "/api/factura":
            self.send_error(404)
            return

        # Leemos lo que mandó la página (un texto JSON)
        largo = int(self.headers.get("Content-Length", 0))
        if largo > 10_000:                      # una factura pesa muy poco; más que esto no es normal
            self.send_error(413)
            return
        try:
            datos = json.loads(self.rfile.read(largo))
        except ValueError:                      # no era un JSON válido
            datos = {}

        factura, error = validar_factura(datos)
        respuesta = {"ok": False, "error": error} if error else {"ok": True, "factura": factura}
        self.responder_json(respuesta)

    def responder_json(self, contenido):
        cuerpo = json.dumps(contenido).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(cuerpo)))
        self.end_headers()
        self.wfile.write(cuerpo)


def main():
    # `directory=CARPETA` hace que sirva los archivos del proyecto sin importar desde dónde se ejecute
    manejador = functools.partial(Manejador, directory=CARPETA)
    servidor = HTTPServer(("127.0.0.1", PUERTO), manejador)

    direccion = f"http://localhost:{PUERTO}"
    print(f"Water Controller Smart funcionando en {direccion}  (Ctrl + C para apagar)")
    webbrowser.open(direccion)                  # abre el navegador solo

    try:
        servidor.serve_forever()
    except KeyboardInterrupt:
        print("\nServidor apagado.")


if __name__ == "__main__":
    main()
