"""Envío de correos de alerta (US-004).

Se creó este módulo aparte para que app.py no dependa de cómo se envía el
correo. Usa solo `smtplib`, que ya viene con Python.

El servicio se configura con variables de entorno (nada de contraseñas
dentro del código):

    WCS_SMTP_SERVIDOR   ej. smtp.gmail.com
    WCS_SMTP_PUERTO     587 (STARTTLS, por defecto) o 465 (SSL)
    WCS_SMTP_USUARIO    cuenta con la que se inicia sesión
    WCS_SMTP_CLAVE      contraseña o contraseña de aplicación
    WCS_SMTP_REMITENTE  opcional; por defecto es el usuario
"""
import os
import smtplib
from email.message import EmailMessage

# Segundos que se espera al servidor de correo antes de darlo por caído.
TIEMPO_ESPERA = 5


def enviar_correo(destino, asunto, cuerpo):
    """Intenta enviar un correo. Devuelve (True, None) o (False, motivo).

    Nunca lanza excepciones: si el servicio falla, app.py recibe el motivo
    y muestra el aviso en el banner de la aplicación web.
    """
    servidor = os.environ.get("WCS_SMTP_SERVIDOR")

    if not servidor:
        # Sin configuración se muestra el correo en la consola para poder
        # probar y se informa del fallo para que salga el banner.
        print(f"[correo no configurado] Para {destino}: {asunto}")
        return False, "El servicio de correo no está configurado."

    usuario = os.environ.get("WCS_SMTP_USUARIO")
    clave = os.environ.get("WCS_SMTP_CLAVE")
    remitente = os.environ.get("WCS_SMTP_REMITENTE") or usuario

    try:
        puerto = int(os.environ.get("WCS_SMTP_PUERTO", "587"))

        mensaje = EmailMessage()
        mensaje["Subject"] = asunto
        mensaje["From"] = remitente or "water-controller@localhost"
        mensaje["To"] = destino
        mensaje.set_content(cuerpo)

        if puerto == 465:
            conexion = smtplib.SMTP_SSL(
                servidor, puerto, timeout=TIEMPO_ESPERA
            )
        else:
            conexion = smtplib.SMTP(
                servidor, puerto, timeout=TIEMPO_ESPERA
            )

        with conexion:
            if puerto != 465:
                conexion.starttls()
            if usuario and clave:
                conexion.login(usuario, clave)
            conexion.send_message(mensaje)

    except (OSError, ValueError, smtplib.SMTPException):
        return False, "El servicio de correo no respondió."

    return True, None