"""Datos de ejemplo para probar la racha, las insignias y los consejos.

Carga actividades de los últimos 10 días en una cuenta que ya exista:

    python datos_demo.py tu_correo@ejemplo.com          (carga los datos)
    python datos_demo.py tu_correo@ejemplo.com --borrar (quita solo los de ejemplo)

Patrón que se crea (hoy queda vacío para poder registrar tú mismo):
    hace 1 a 5 días  -> dentro de la meta  (racha de 5 días)
    hace 6 días      -> se pasa de la meta (rompe la racha)
    hace 7 a 10 días -> dentro de la meta  (otra racha de 4)
Los registros de ejemplo se marcan con "[demo]" para poder borrarlos sin tocar
tus datos reales. Si lo ejecutas dos veces, primero borra los anteriores.
"""
import sys
from datetime import datetime, timedelta

import db
from app import app

# (actividad, nombre, caudal estándar, tiempo recomendado, minutos base)
ACTIVIDADES = [
    ("ducha", "Ducha", 9.0, 5, 7.0),
    ("platos", "Lavado de platos", 6.0, 10, 4.0),
    ("riego", "Riego", 12.0, 15, 3.0),
]
LITROS_BASE = sum(caudal * minutos for _, _, caudal, _, minutos in ACTIVIDADES)


def borrar_demo(usuario_id):
    bd = db.obtener_bd()
    cursor = bd.execute(
        "DELETE FROM actividades WHERE usuario_id = ? AND mensaje LIKE '[demo]%'",
        (usuario_id,),
    )
    bd.commit()
    return cursor.rowcount


def cargar_demo(usuario_id, meta):
    insertadas = 0
    hoy = datetime.now().date()

    for dias_atras in range(1, 11):
        # Se escala el consumo según la meta del usuario: 85% si cumple, 140% si se pasa
        factor = (1.4 if dias_atras == 6 else 0.85) * meta / LITROS_BASE
        dia = hoy - timedelta(days=dias_atras)

        for orden, (clave, nombre, caudal, recomendado, base) in enumerate(ACTIVIDADES):
            minutos = round(base * factor, 2)
            litros = round(minutos * caudal, 2)
            db.insertar_actividad(usuario_id, {
                "actividad": clave,
                "nombre": nombre,
                "fecha": dia.isoformat(),
                "hora": f"{7 + orden * 4:02d}:00:00",
                "minutos": minutos,
                "caudal": caudal,
                "caudal_personalizado": False,
                "litros": litros,
                "tiempo_recomendado": recomendado,
                "ahorro_litros": round(max(0.0, minutos - recomendado) * caudal, 2),
                "origen": "cronometro",
                "mensaje": f"[demo] {nombre}: {litros} L",
                "exceso_tiempo": minutos > recomendado,
            })
            insertadas += 1

    return insertadas


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        return 1

    correo = sys.argv[1].strip().lower()

    with app.app_context():
        usuario = db.buscar_usuario_por_correo(correo)
        if usuario is None:
            print(f"No existe la cuenta {correo}. Primero créala en la aplicación.")
            return 1

        borradas = borrar_demo(usuario["id"])

        if "--borrar" in sys.argv:
            print(f"Se borraron {borradas} registros de ejemplo.")
            return 0

        meta = db.cargar_datos(usuario["id"])["meta_diaria"]
        insertadas = cargar_demo(usuario["id"], meta)

    print(f"Listo: se cargaron {insertadas} actividades de ejemplo para {correo} (meta {meta} L).")
    print("Abre el panel y recarga con Ctrl+F5: racha actual 5, mejor racha 5.")
    return 0


if __name__ == "__main__":
    sys.exit(main())