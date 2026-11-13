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

Se agregó un diseño HTML al correo (con una versión en texto plano para los
programas de correo que no muestran HTML).
"""
import os
import smtplib
from email.message import EmailMessage
from html import escape

# Segundos que se espera al servidor de correo antes de darlo por caído.
TIEMPO_ESPERA = 5

# Se definió el aspecto de cada tipo de alerta: color, título y emoji.
ESTILOS = {
    "preventiva": {
        "color": "#ffc107",
        "texto": "#664d03",
        "fondo": "#fff3cd",
        "etiqueta": "Alerta preventiva",
        "titulo": "Estás cerca de tu meta diaria",
        "icono": "⚠️",
    },
    "correctiva": {
        "color": "#dc3545",
        "texto": "#842029",
        "fondo": "#f8d7da",
        "etiqueta": "Alerta de exceso",
        "titulo": "Superaste tu meta diaria",
        "icono": "🚨",
    },
}


def construir_html(mensaje, nivel):
    """Se creó la plantilla del correo.

    Usa tablas y estilos en línea porque Gmail, Outlook y otros programas
    ignoran la mayoría del CSS externo.
    """
    estilo = ESTILOS.get(nivel, ESTILOS["preventiva"])
    texto = escape(mensaje)

    return f"""\
<!doctype html>
<html lang="es">
<body style="margin:0;padding:0;background:#f1f5f9;">
  <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:#f1f5f9;padding:24px 12px;">
    <tr><td align="center">
      <table role="presentation" width="560" cellpadding="0" cellspacing="0" style="max-width:560px;width:100%;background:#ffffff;border-radius:12px;overflow:hidden;border:1px solid #e2e8f0;font-family:Arial,Helvetica,sans-serif;">

        <tr><td style="background:#0c4a6e;padding:20px 28px;color:#ffffff;">
          <div style="font-size:20px;font-weight:bold;">💧 Water Controller Smart</div>
          <div style="font-size:13px;color:#94c7e8;margin-top:4px;">Control inteligente de tu consumo de agua</div>
        </td></tr>

        <tr><td style="padding:28px;">
          <span style="display:inline-block;background:{estilo['fondo']};color:{estilo['texto']};border:1px solid {estilo['color']};border-radius:99px;padding:4px 12px;font-size:12px;font-weight:bold;">
            {estilo['icono']} {estilo['etiqueta']}
          </span>

          <h1 style="font-size:22px;color:#0f172a;margin:16px 0 8px 0;">{estilo['titulo']}</h1>

          <div style="background:{estilo['fondo']};border-left:4px solid {estilo['color']};border-radius:6px;padding:14px 16px;color:{estilo['texto']};font-size:15px;line-height:1.5;">
            {texto}
          </div>

          <p style="font-size:14px;color:#475569;line-height:1.5;margin:20px 0 0 0;">
            Entra a tu panel para revisar tus actividades de hoy y ajustar tu consumo.
          </p>
        </td></tr>

        <tr><td style="background:#f8fafc;border-top:1px solid #e2e8f0;padding:16px 28px;font-size:12px;color:#64748b;line-height:1.5;">
          Recibes este correo porque tienes una cuenta en Water Controller Smart.
          Puedes cambiar tu meta diaria y el porcentaje de aviso en la sección Configuración.
        </td></tr>

      </table>
    </td></tr>
  </table>
</body>
</html>
"""


def enviar_correo(destino, asunto, cuerpo, nivel="preventiva", html=None):
    """Intenta enviar un correo. Devuelve (True, None) o (False, motivo).

    Nunca lanza excepciones: si el servicio falla, app.py recibe el motivo
    y muestra el aviso en el banner de la aplicación web.
    `nivel` ("preventiva" o "correctiva") elige los colores del diseño.
    `html` (opcional) es un diseño ya armado, por ejemplo el del resumen semanal.
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
        # Versión en texto plano (la que se veía antes) y versión con diseño.
        mensaje.set_content(cuerpo)
        mensaje.add_alternative(
            html or construir_html(cuerpo, nivel), subtype="html"
        )

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