# ============================================================
# gmail.py — Integración con Gmail para Eli
#
# Usa google_auth.py para autenticación compartida con Calendar.
# Todas las respuestas son cortas y naturales para voz.
#
# La API de Gmail trabaja con "mensajes" que tienen un ID único.
# Para leer un email necesitas 2 pasos:
#   1. Listar IDs con messages().list()
#   2. Obtener el contenido con messages().get() por cada ID
# ============================================================

import base64
from email.mime.text import MIMEText
from googleapiclient.errors import HttpError

from google_auth import obtener_servicio_gmail

USUARIO = "me"  # alias que la API usa para el usuario autenticado


# ============================================================
# FUNCIONES DE CONSULTA
# ============================================================

def contar_no_leidos():
    """Cuenta los emails no leídos en la bandeja de entrada."""
    try:
        servicio = obtener_servicio_gmail()

        resultado = servicio.users().messages().list(
            userId=USUARIO,
            q="is:unread",
            labelIds=["INBOX"],
            maxResults=1
        ).execute()

        total = resultado.get("resultSizeEstimate", 0)

        if total == 0:
            return "No tienes emails sin leer. Tu bandeja está limpia."
        elif total == 1:
            return "Tienes 1 email sin leer."
        else:
            return f"Tienes aproximadamente {total} emails sin leer."

    except HttpError as error:
        return f"Error al consultar Gmail: {error}"
    except Exception as error:
        return f"No pude acceder a Gmail: {error}"


def leer_emails_recientes(cantidad=5):
    """
    Lee los últimos N emails no leídos.
    Solo muestra remitente + asunto (no el cuerpo) para ser apto para voz.
    """
    try:
        servicio = obtener_servicio_gmail()

        resultado = servicio.users().messages().list(
            userId=USUARIO,
            q="is:unread",
            labelIds=["INBOX"],
            maxResults=min(cantidad, 10)
        ).execute()

        mensajes = resultado.get("messages", [])

        if not mensajes:
            return "No tienes emails nuevos."

        resumen = []
        for msg in mensajes:
            detalle = _obtener_resumen_email(servicio, msg["id"])
            if detalle:
                resumen.append(detalle)

        total = len(resumen)
        intro = f"Tienes {total} email{'s' if total > 1 else ''} sin leer. "

        if total <= 3:
            return f"{intro}{'. '.join(resumen)}."
        else:
            primeros = ". ".join(resumen[:3])
            return f"{intro}Los más recientes: {primeros}. Y {total - 3} más."

    except HttpError as error:
        return f"Error al leer emails: {error}"
    except Exception as error:
        return f"No pude leer los emails: {error}"


def leer_email_importante():
    """Lee emails importantes (marcados por Gmail) o con estrella."""
    try:
        servicio = obtener_servicio_gmail()

        resultado = servicio.users().messages().list(
            userId=USUARIO,
            q="is:unread (is:important OR is:starred)",
            labelIds=["INBOX"],
            maxResults=5
        ).execute()

        mensajes = resultado.get("messages", [])

        if not mensajes:
            return "No tienes emails importantes sin leer."

        resumen = []
        for msg in mensajes:
            detalle = _obtener_resumen_email(servicio, msg["id"])
            if detalle:
                resumen.append(detalle)

        total = len(resumen)
        intro = f"Tienes {total} email{'s' if total > 1 else ''} importante{'s' if total > 1 else ''}. "
        return f"{intro}{'. '.join(resumen[:3])}."

    except HttpError as error:
        return f"Error al leer emails importantes: {error}"
    except Exception as error:
        return f"No pude leer los emails: {error}"


def buscar_email(query):
    """
    Busca emails. Acepta sintaxis de Gmail: "from:nombre", "subject:texto", etc.
    """
    try:
        servicio = obtener_servicio_gmail()

        resultado = servicio.users().messages().list(
            userId=USUARIO,
            q=query,
            maxResults=5
        ).execute()

        mensajes = resultado.get("messages", [])

        if not mensajes:
            return f"No encontré emails que coincidan con '{query}'."

        resumen = []
        for msg in mensajes:
            detalle = _obtener_resumen_email(servicio, msg["id"])
            if detalle:
                resumen.append(detalle)

        total = len(resumen)
        return f"Encontré {total} resultado{'s' if total > 1 else ''}. {'. '.join(resumen[:3])}."

    except HttpError as error:
        return f"Error al buscar emails: {error}"
    except Exception as error:
        return f"No pude buscar en Gmail: {error}"


# ============================================================
# ENVIAR EMAIL
# ============================================================

def enviar_email(destinatario, asunto, cuerpo):
    """
    Envía un email desde la cuenta del usuario.

    Args:
        destinatario (str): Email del destinatario.
        asunto (str): Asunto del email.
        cuerpo (str): Contenido del email (texto plano).
    """
    try:
        servicio = obtener_servicio_gmail()

        mensaje = MIMEText(cuerpo)
        mensaje["to"] = destinatario
        mensaje["subject"] = asunto

        texto_codificado = base64.urlsafe_b64encode(
            mensaje.as_string().encode("utf-8")
        ).decode("utf-8")

        servicio.users().messages().send(
            userId=USUARIO,
            body={"raw": texto_codificado}
        ).execute()

        return f"Email enviado a {destinatario} con asunto '{asunto}'."

    except HttpError as error:
        return f"Error al enviar el email: {error}"
    except Exception as error:
        return f"No pude enviar el email: {error}"


# ============================================================
# UTILIDADES INTERNAS
# ============================================================

def _obtener_resumen_email(servicio, msg_id):
    """
    Obtiene remitente + asunto de un email. Usa format="metadata"
    para descargar solo los headers (más rápido que "full").
    """
    try:
        msg = servicio.users().messages().get(
            userId=USUARIO,
            id=msg_id,
            format="metadata",
            metadataHeaders=["From", "Subject"]
        ).execute()

        headers = msg.get("payload", {}).get("headers", [])
        remitente = ""
        asunto = ""

        for header in headers:
            nombre = header.get("name", "").lower()
            valor = header.get("value", "")
            if nombre == "from":
                # "Nombre Apellido <email@domain.com>" → solo el nombre
                remitente = valor.split("<")[0].strip().strip('"') if "<" in valor else valor
            elif nombre == "subject":
                asunto = valor

        remitente = remitente or "remitente desconocido"
        asunto = asunto or "sin asunto"
        return f"De {remitente}, asunto: {asunto}"

    except Exception:
        return None


# --- Prueba directa ---
if __name__ == "__main__":
    print("=== Prueba de Gmail ===\n")
    print(f"No leídos:    {contar_no_leidos()}\n")
    print(f"Recientes:    {leer_emails_recientes(3)}\n")
    print(f"Importantes:  {leer_email_importante()}\n")
    print(f"Buscar:       {buscar_email('from:google')}\n")
