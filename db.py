"""Capa de base de datos de Water Controller Smart (SQLite).

Se creó este archivo para reemplazar el antiguo datos.json. Se usa solo la
librería estándar `sqlite3` (sin ORM): cada función hace una consulta SQL
sencilla y devuelve diccionarios de Python.

Todas las tablas de datos guardan `usuario_id`, una llave foránea hacia la
tabla `usuarios`. Así cada persona solo ve y modifica lo suyo:

    usuarios ──< configuracion        (meta diaria y % de aviso)
             ──< personalizaciones    (caudal y tiempo recomendado propios)
             ──< cronometros          (cronómetro en marcha, máximo uno)
             ──< actividades          (registros de consumo)
             ──< alertas              (US-004: registro de alertas)
"""
import os
import sqlite3
from datetime import datetime

from flask import g

CARPETA = os.path.dirname(os.path.abspath(__file__))
ARCHIVO_BD = os.path.join(CARPETA, "water.db")

# Se definieron aquí los valores con los que empieza cada usuario nuevo.
META_DIARIA_PREDETERMINADA = 100.0
PORCENTAJE_AVISO_PREDETERMINADO = 80

ESQUEMA = """
CREATE TABLE IF NOT EXISTS usuarios (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    correo          TEXT NOT NULL UNIQUE,
    contrasena_hash TEXT NOT NULL,
    creado          TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS configuracion (
    usuario_id       INTEGER PRIMARY KEY
                     REFERENCES usuarios(id) ON DELETE CASCADE,
    meta_diaria      REAL NOT NULL,
    porcentaje_aviso INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS personalizaciones (
    usuario_id         INTEGER NOT NULL
                       REFERENCES usuarios(id) ON DELETE CASCADE,
    actividad          TEXT NOT NULL,
    caudal             REAL,
    tiempo_recomendado REAL,
    PRIMARY KEY (usuario_id, actividad)
);

CREATE TABLE IF NOT EXISTS cronometros (
    usuario_id INTEGER PRIMARY KEY
               REFERENCES usuarios(id) ON DELETE CASCADE,
    actividad  TEXT NOT NULL,
    inicio     REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS actividades (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    usuario_id          INTEGER NOT NULL
                        REFERENCES usuarios(id) ON DELETE CASCADE,
    actividad           TEXT NOT NULL,
    nombre              TEXT NOT NULL,
    fecha               TEXT NOT NULL,
    hora                TEXT NOT NULL,
    minutos             REAL NOT NULL,
    caudal              REAL NOT NULL,
    caudal_personalizado INTEGER NOT NULL DEFAULT 0,
    litros              REAL NOT NULL,
    tiempo_recomendado  REAL NOT NULL,
    ahorro_litros       REAL NOT NULL DEFAULT 0,
    origen              TEXT NOT NULL,
    mensaje             TEXT NOT NULL,
    exceso_tiempo       INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS indice_actividades_usuario_fecha
    ON actividades (usuario_id, fecha);

CREATE TABLE IF NOT EXISTS alertas (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    usuario_id    INTEGER NOT NULL
                  REFERENCES usuarios(id) ON DELETE CASCADE,
    actividad_id  INTEGER
                  REFERENCES actividades(id) ON DELETE SET NULL,
    tipo          TEXT NOT NULL,
    nivel         TEXT NOT NULL,
    mensaje       TEXT NOT NULL,
    fecha         TEXT NOT NULL,
    hora          TEXT NOT NULL,
    correo_estado TEXT NOT NULL,
    correo_error  TEXT
);
CREATE INDEX IF NOT EXISTS indice_alertas_usuario
    ON alertas (usuario_id, id);

    
CREATE TABLE IF NOT EXISTS actividades_personalizadas (
    id                  TEXT PRIMARY KEY,
    usuario_id          INTEGER NOT NULL
                        REFERENCES usuarios(id) ON DELETE CASCADE,
    nombre              TEXT NOT NULL,
    caudal              REAL NOT NULL,
    tiempo_recomendado  REAL NOT NULL,
    activa              INTEGER NOT NULL DEFAULT 1,
    UNIQUE (usuario_id, nombre COLLATE NOCASE)
);

"""


# ---------- Conexión ----------

def obtener_bd():
    """Devuelve la conexión de la petición actual (se abre una sola vez)."""
    if "bd" not in g:
        conexion = sqlite3.connect(ARCHIVO_BD)
        conexion.row_factory = sqlite3.Row
        # SQLite no revisa las llaves foráneas si no se activa esto.
        conexion.execute("PRAGMA foreign_keys = ON")
        g.bd = conexion
    return g.bd


def cerrar_bd(_error=None):
    """Se registró en Flask para cerrar la conexión al terminar la petición."""
    conexion = g.pop("bd", None)
    if conexion is not None:
        conexion.close()


def iniciar_bd(app):
    """Crea las tablas si no existen y conecta el cierre automático."""
    app.teardown_appcontext(cerrar_bd)
    with app.app_context():
        obtener_bd().executescript(ESQUEMA)


def ahora():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


# ---------- Usuarios (login) ----------

def crear_usuario(correo, contrasena_hash):
    """Crea el usuario y su configuración inicial.

    Devuelve el id nuevo, o None si el correo ya estaba registrado.
    """
    bd = obtener_bd()
    try:
        cursor = bd.execute(
            "INSERT INTO usuarios (correo, contrasena_hash, creado) "
            "VALUES (?, ?, ?)",
            (correo, contrasena_hash, ahora()),
        )
    except sqlite3.IntegrityError:
        return None

    usuario_id = cursor.lastrowid
    bd.execute(
        "INSERT INTO configuracion (usuario_id, meta_diaria, "
        "porcentaje_aviso) VALUES (?, ?, ?)",
        (
            usuario_id,
            META_DIARIA_PREDETERMINADA,
            PORCENTAJE_AVISO_PREDETERMINADO,
        ),
    )
    bd.commit()
    return usuario_id


def buscar_usuario_por_correo(correo):
    fila = obtener_bd().execute(
        "SELECT * FROM usuarios WHERE correo = ?", (correo,)
    ).fetchone()
    return dict(fila) if fila else None


def buscar_usuario(usuario_id):
    fila = obtener_bd().execute(
        "SELECT * FROM usuarios WHERE id = ?", (usuario_id,)
    ).fetchone()
    return dict(fila) if fila else None


# ---------- Lectura de datos (misma forma que tenía el JSON) ----------

def cargar_datos(usuario_id):
    """Arma el diccionario con todo lo del usuario.

    Se conservó la misma estructura que tenía datos.json
    (actividades, caudales, tiempos_recomendados, meta_diaria, cronometro)
    para que los cálculos de app.py no cambiaran.
    """
    bd = obtener_bd()

    actividades = []
    filas = bd.execute(
        "SELECT * FROM actividades WHERE usuario_id = ? ORDER BY id",
        (usuario_id,),
    ).fetchall()
    for fila in filas:
        registro = dict(fila)
        registro.pop("usuario_id")
        registro["caudal_personalizado"] = bool(
            registro["caudal_personalizado"]
        )
        registro["exceso_tiempo"] = bool(registro["exceso_tiempo"])
        actividades.append(registro)

    caudales = {}
    tiempos = {}
    filas = bd.execute(
        "SELECT actividad, caudal, tiempo_recomendado "
        "FROM personalizaciones WHERE usuario_id = ?",
        (usuario_id,),
    ).fetchall()
    for fila in filas:
        if fila["caudal"] is not None:
            caudales[fila["actividad"]] = fila["caudal"]
        if fila["tiempo_recomendado"] is not None:
            tiempos[fila["actividad"]] = fila["tiempo_recomendado"]

    config = bd.execute(
        "SELECT meta_diaria, porcentaje_aviso FROM configuracion "
        "WHERE usuario_id = ?",
        (usuario_id,),
    ).fetchone()

    crono = bd.execute(
        "SELECT actividad, inicio FROM cronometros WHERE usuario_id = ?",
        (usuario_id,),
    ).fetchone()

    personalizadas = {}
    filas = bd.execute(
        "SELECT id, nombre, caudal, tiempo_recomendado, activa "
        "FROM actividades_personalizadas WHERE usuario_id = ?",
        (usuario_id,),
    ).fetchall()
    for fila in filas:
        personalizadas[fila["id"]] = {
            "nombre": fila["nombre"],
            "caudal": fila["caudal"],
            "tiempo_recomendado": fila["tiempo_recomendado"],
            "activa": bool(fila["activa"]),
        }



    return {
        "actividades": actividades,
        "caudales": caudales,
        "tiempos_recomendados": tiempos,
        "meta_diaria": (
            config["meta_diaria"] if config
            else META_DIARIA_PREDETERMINADA
        ),
        "porcentaje_aviso": (
            config["porcentaje_aviso"] if config
            else PORCENTAJE_AVISO_PREDETERMINADO
        ),
        "cronometro": dict(crono) if crono else None,
        "personalizadas": personalizadas,
    }


# ---------- Actividades ----------

def insertar_actividad(usuario_id, r, confirmar=True):
    """Guarda un registro de consumo y devuelve su id."""
    bd = obtener_bd()
    cursor = bd.execute(
        "INSERT INTO actividades (usuario_id, actividad, nombre, fecha, "
        "hora, minutos, caudal, caudal_personalizado, litros, "
        "tiempo_recomendado, ahorro_litros, origen, mensaje, "
        "exceso_tiempo) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (
            usuario_id, r["actividad"], r["nombre"], r["fecha"],
            r["hora"], r["minutos"], r["caudal"],
            int(r["caudal_personalizado"]), r["litros"],
            r["tiempo_recomendado"], r["ahorro_litros"], r["origen"],
            r["mensaje"], int(r.get("exceso_tiempo", False)),
        ),
    )
    if confirmar:
        bd.commit()
    return cursor.lastrowid


# ---------- Personalización y configuración ----------

def guardar_personalizacion(usuario_id, actividad, campo, valor):
    """Guarda (o borra si valor es None) el caudal o el tiempo recomendado.

    `campo` solo puede ser "caudal" o "tiempo_recomendado"; se revisa
    contra una lista fija porque el nombre de la columna no puede ir como
    parámetro en SQL.
    """
    if campo not in ("caudal", "tiempo_recomendado"):
        raise ValueError("Campo no permitido")

    bd = obtener_bd()
    bd.execute(
        "INSERT INTO personalizaciones (usuario_id, actividad) "
        "VALUES (?, ?) ON CONFLICT(usuario_id, actividad) DO NOTHING",
        (usuario_id, actividad),
    )
    bd.execute(
        f"UPDATE personalizaciones SET {campo} = ? "
        "WHERE usuario_id = ? AND actividad = ?",
        (valor, usuario_id, actividad),
    )
    # Si ya no queda nada personalizado, se elimina la fila vacía.
    bd.execute(
        "DELETE FROM personalizaciones WHERE usuario_id = ? "
        "AND actividad = ? AND caudal IS NULL "
        "AND tiempo_recomendado IS NULL",
        (usuario_id, actividad),
    )
    bd.commit()

def crear_actividad_personalizada(usuario_id, actividad_id, nombre,
                                  caudal, tiempo_recomendado):
    """Guarda una actividad creada por el usuario."""
    bd = obtener_bd()

    try:
        bd.execute(
            "INSERT INTO actividades_personalizadas "
            "(id, usuario_id, nombre, caudal, tiempo_recomendado) "
            "VALUES (?, ?, ?, ?, ?)",
            (
                actividad_id,
                usuario_id,
                nombre,
                caudal,
                tiempo_recomendado,
            ),
        )
        bd.commit()
        return True

    except sqlite3.IntegrityError:
        return False

def listar_actividades_personalizadas(usuario_id):
    """Devuelve las actividades personalizadas del usuario."""
    filas = obtener_bd().execute(
        "SELECT * FROM actividades_personalizadas "
        "WHERE usuario_id = ? AND activa = 1 "
        "ORDER BY nombre COLLATE NOCASE",
        (usuario_id,),
    ).fetchall()

    return [dict(fila) for fila in filas]


def buscar_actividad_personalizada(usuario_id, actividad_id):
    """Busca una actividad perteneciente al usuario."""
    fila = obtener_bd().execute(
        "SELECT * FROM actividades_personalizadas "
        "WHERE usuario_id = ? AND id = ? AND activa = 1",
        (usuario_id, actividad_id),
    ).fetchone()

    return dict(fila) if fila else None

def contar_actividades_personalizadas(usuario_id):
    """Cuántas actividades propias activas tiene el usuario."""
    fila = obtener_bd().execute(
        "SELECT COUNT(*) AS total FROM actividades_personalizadas "
        "WHERE usuario_id = ? AND activa = 1",
        (usuario_id,),
    ).fetchone()
    return fila["total"]


def actualizar_campo_personalizada(usuario_id, actividad_id, campo, valor):
    """Cambia el caudal o el tiempo recomendado de una actividad propia."""
    if campo not in ("caudal", "tiempo_recomendado"):
        raise ValueError("Campo no permitido")

    bd = obtener_bd()
    cursor = bd.execute(
        f"UPDATE actividades_personalizadas SET {campo} = ? "
        "WHERE usuario_id = ? AND id = ? AND activa = 1",
        (valor, usuario_id, actividad_id),
    )
    bd.commit()
    return cursor.rowcount > 0


def desactivar_actividad_personalizada(usuario_id, actividad_id):
    """Borrado lógico: el historial conserva el nombre copiado.

    Se le agrega un sufijo al nombre para liberarlo, porque el UNIQUE
    (usuario_id, nombre) también cuenta las actividades inactivas.
    """
    bd = obtener_bd()
    cursor = bd.execute(
        "UPDATE actividades_personalizadas "
        "SET activa = 0, nombre = nombre || ' [eliminada ' || id || ']' "
        "WHERE usuario_id = ? AND id = ? AND activa = 1",
        (usuario_id, actividad_id),
    )
    bd.commit()
    return cursor.rowcount > 0


def guardar_meta_diaria(usuario_id, meta):
    bd = obtener_bd()
    bd.execute(
        "UPDATE configuracion SET meta_diaria = ? WHERE usuario_id = ?",
        (meta, usuario_id),
    )
    bd.commit()


def guardar_porcentaje_aviso(usuario_id, porcentaje):
    bd = obtener_bd()
    bd.execute(
        "UPDATE configuracion SET porcentaje_aviso = ? "
        "WHERE usuario_id = ?",
        (porcentaje, usuario_id),
    )
    bd.commit()


# ---------- Cronómetro ----------

def iniciar_cronometro(usuario_id, actividad, inicio):
    """Devuelve False si el usuario ya tenía un cronómetro en marcha."""
    bd = obtener_bd()
    try:
        bd.execute(
            "INSERT INTO cronometros (usuario_id, actividad, inicio) "
            "VALUES (?, ?, ?)",
            (usuario_id, actividad, inicio),
        )
    except sqlite3.IntegrityError:
        return False
    bd.commit()
    return True


def borrar_cronometro(usuario_id, confirmar=True):
    """Quita el cronómetro; devuelve True si había uno que quitar."""
    bd = obtener_bd()
    cursor = bd.execute(
        "DELETE FROM cronometros WHERE usuario_id = ?", (usuario_id,)
    )
    if confirmar:
        bd.commit()
    return cursor.rowcount > 0


# ---------- Alertas (US-004) ----------

def insertar_alerta(usuario_id, actividad_id, tipo, nivel, mensaje,
                    momento, confirmar=True):
    bd = obtener_bd()
    cursor = bd.execute(
        "INSERT INTO alertas (usuario_id, actividad_id, tipo, nivel, "
        "mensaje, fecha, hora, correo_estado) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, 'no_aplica')",
        (
            usuario_id, actividad_id, tipo, nivel, mensaje,
            momento.strftime("%Y-%m-%d"), momento.strftime("%H:%M:%S"),
        ),
    )
    if confirmar:
        bd.commit()
    return cursor.lastrowid


def actualizar_correo_alerta(alerta_id, estado, error=None):
    bd = obtener_bd()
    bd.execute(
        "UPDATE alertas SET correo_estado = ?, correo_error = ? "
        "WHERE id = ?",
        (estado, error, alerta_id),
    )
    bd.commit()


def listar_alertas(usuario_id, limite=200):
    filas = obtener_bd().execute(
        "SELECT id, tipo, nivel, mensaje, fecha, hora, correo_estado, "
        "correo_error FROM alertas WHERE usuario_id = ? "
        "ORDER BY id DESC LIMIT ?",
        (usuario_id, limite),
    ).fetchall()
    return [dict(fila) for fila in filas]