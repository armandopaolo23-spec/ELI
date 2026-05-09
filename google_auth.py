# ============================================================
# google_auth.py — Autenticación compartida de Google para Eli
#
# Centraliza OAuth para Calendar y Gmail. Ambos usan el mismo
# token.json con todos los permisos. Si agregas más APIs de
# Google (Drive, Sheets, etc.), solo agrega el scope aquí y
# borra token.json para regenerarlo.
# ============================================================

import os
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

RUTA_CREDENTIALS = os.path.join(os.path.dirname(__file__), "credentials.json")
RUTA_TOKEN = os.path.join(os.path.dirname(__file__), "token.json")

SCOPES = [
    "https://www.googleapis.com/auth/calendar",
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/gmail.send",
    "https://www.googleapis.com/auth/gmail.modify",
]


def obtener_credenciales():
    """
    Obtiene credenciales OAuth válidas.

    1. Si existe token.json, lo carga.
    2. Si expiró, lo renueva con el refresh token.
    3. Si no existe, abre el navegador para autorizar.
    """
    creds = None

    if os.path.exists(RUTA_TOKEN):
        creds = Credentials.from_authorized_user_file(RUTA_TOKEN, SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            if not os.path.exists(RUTA_CREDENTIALS):
                raise FileNotFoundError(
                    f"No encontré {RUTA_CREDENTIALS}. "
                    "Descárgalo de Google Cloud Console."
                )
            flow = InstalledAppFlow.from_client_secrets_file(
                RUTA_CREDENTIALS, SCOPES
            )
            creds = flow.run_local_server(port=0)

        with open(RUTA_TOKEN, "w") as f:
            f.write(creds.to_json())

    return creds


def obtener_servicio_calendar():
    """Retorna el servicio autenticado de Google Calendar."""
    creds = obtener_credenciales()
    return build("calendar", "v3", credentials=creds)


def obtener_servicio_gmail():
    """Retorna el servicio autenticado de Gmail."""
    creds = obtener_credenciales()
    return build("gmail", "v1", credentials=creds)
