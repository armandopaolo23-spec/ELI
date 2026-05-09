# ============================================================
# google_calendar.py — Integración con Google Calendar para Eli
#
# Usa google_auth.py para autenticación compartida con Gmail.
# ============================================================

import datetime
from googleapiclient.errors import HttpError
from google_auth import obtener_servicio_calendar


# ============================================================
# FUNCIONES DE CONSULTA
# ============================================================

def ver_eventos_hoy():
    """
    Lista los eventos de hoy.

    Retorna:
        str: Texto con los eventos para que Eli lo diga.
    """
    hoy = datetime.date.today()
    return _eventos_del_dia(hoy, "hoy")


def ver_eventos_manana():
    """Lista los eventos de mañana."""
    manana = datetime.date.today() + datetime.timedelta(days=1)
    return _eventos_del_dia(manana, "mañana")


def proximos_eventos(dias=7):
    """
    Lista eventos de los próximos N días.

    Args:
        dias (int): Cuántos días hacia adelante buscar.

    Retorna:
        str: Texto con los eventos agrupados por día.
    """
    try:
        servicio = obtener_servicio_calendar()

        ahora = datetime.datetime.now(datetime.timezone.utc)
        limite = ahora + datetime.timedelta(days=dias)

        # calendarId="primary" = el calendario principal del usuario.
        # timeMin/timeMax filtran el rango de fechas.
        # singleEvents=True expande eventos recurrentes en instancias individuales.
        # orderBy="startTime" los ordena cronológicamente.
        resultado = servicio.events().list(
            calendarId="primary",
            timeMin=ahora.isoformat(),
            timeMax=limite.isoformat(),
            singleEvents=True,
            orderBy="startTime",
            maxResults=20
        ).execute()

        eventos = resultado.get("items", [])

        if not eventos:
            return f"No tienes eventos en los próximos {dias} días."

        # Agrupar por día para una respuesta más natural.
        lineas = []
        dia_anterior = ""

        for evento in eventos:
            inicio = evento["start"].get("dateTime", evento["start"].get("date", ""))
            titulo = evento.get("summary", "Sin título")

            # Parsear la fecha para agrupar.
            if "T" in inicio:
                # Evento con hora específica.
                dt = datetime.datetime.fromisoformat(inicio)
                dia = dt.strftime("%A %d")
                hora = dt.strftime("%I:%M %p")
                texto_evento = f"{hora}: {titulo}"
            else:
                # Evento de día completo.
                dt = datetime.date.fromisoformat(inicio)
                dia = dt.strftime("%A %d")
                texto_evento = f"Todo el día: {titulo}"

            # Si cambió el día, agregar separador.
            if dia != dia_anterior:
                lineas.append(f"{dia}.")
                dia_anterior = dia

            lineas.append(f"  {texto_evento}")

        return "Tus próximos eventos. " + ". ".join(lineas) + "."

    except FileNotFoundError as error:
        return str(error)
    except HttpError as error:
        return f"Error de Google Calendar: {error}"
    except Exception as error:
        return f"Error al consultar el calendario: {error}"


def _eventos_del_dia(fecha, nombre_dia):
    """
    Consulta los eventos de un día específico.

    Args:
        fecha (datetime.date): El día a consultar.
        nombre_dia (str): "hoy" o "mañana" para el mensaje.

    Retorna:
        str: Texto con los eventos del día.
    """
    try:
        servicio = obtener_servicio_calendar()

        # Construir rango: desde las 00:00 hasta las 23:59 del día.
        inicio_dia = datetime.datetime.combine(
            fecha,
            datetime.time.min,
            tzinfo=datetime.timezone.utc
        )
        fin_dia = datetime.datetime.combine(
            fecha,
            datetime.time.max,
            tzinfo=datetime.timezone.utc
        )

        resultado = servicio.events().list(
            calendarId="primary",
            timeMin=inicio_dia.isoformat(),
            timeMax=fin_dia.isoformat(),
            singleEvents=True,
            orderBy="startTime",
            maxResults=15
        ).execute()

        eventos = resultado.get("items", [])

        if not eventos:
            return f"No tienes eventos para {nombre_dia}."

        lineas = []
        for evento in eventos:
            inicio = evento["start"].get("dateTime", evento["start"].get("date", ""))
            titulo = evento.get("summary", "Sin título")

            if "T" in inicio:
                dt = datetime.datetime.fromisoformat(inicio)
                hora = dt.strftime("%I:%M %p")
                lineas.append(f"A las {hora}, {titulo}")
            else:
                lineas.append(f"Todo el día, {titulo}")

        intro = f"Para {nombre_dia} tienes {len(eventos)} evento"
        intro += "s" if len(eventos) > 1 else ""
        return f"{intro}. " + ". ".join(lineas) + "."

    except FileNotFoundError as error:
        return str(error)
    except HttpError as error:
        return f"Error de Google Calendar: {error}"
    except Exception as error:
        return f"Error al consultar el calendario: {error}"


# ============================================================
# CREAR EVENTOS
# ============================================================

def crear_evento(titulo, fecha, hora, duracion_minutos=60):
    """
    Crea un evento en Google Calendar.

    Args:
        titulo (str): Nombre del evento (ej: "Reunión con cliente").
        fecha (str): Fecha en formato "YYYY-MM-DD" (ej: "2025-07-15").
        hora (str): Hora en formato "HH:MM" 24h (ej: "15:00").
        duracion_minutos (int): Duración en minutos (default: 60).

    Retorna:
        str: Confirmación o error.
    """
    try:
        servicio = obtener_servicio_calendar()

        # Construir datetime de inicio.
        inicio_str = f"{fecha}T{hora}:00"
        inicio_dt = datetime.datetime.fromisoformat(inicio_str)

        # Calcular fin.
        fin_dt = inicio_dt + datetime.timedelta(minutes=duracion_minutos)

        # Estructura del evento para la API.
        # timeZone se pone explícito para evitar problemas con UTC.
        evento = {
            "summary": titulo,
            "start": {
                "dateTime": inicio_dt.isoformat(),
                "timeZone": "America/Lima",  # Cajamarca usa hora de Lima.
            },
            "end": {
                "dateTime": fin_dt.isoformat(),
                "timeZone": "America/Lima",
            },
        }

        resultado = servicio.events().insert(
            calendarId="primary",
            body=evento
        ).execute()

        hora_legible = inicio_dt.strftime("%I:%M %p")
        return (
            f"Evento creado: {titulo}, "
            f"el {fecha} a las {hora_legible}, "
            f"duración {duracion_minutos} minutos."
        )

    except FileNotFoundError as error:
        return str(error)
    except HttpError as error:
        return f"Error al crear el evento: {error}"
    except ValueError as error:
        return f"Formato de fecha u hora incorrecto: {error}"
    except Exception as error:
        return f"Error inesperado: {error}"


# ============================================================
# BUSCAR EVENTOS
# ============================================================

def buscar_evento(query):
    """
    Busca eventos por nombre en los próximos 30 días.

    Args:
        query (str): Texto a buscar en el título del evento.

    Retorna:
        str: Eventos encontrados o mensaje de no encontrado.
    """
    try:
        servicio = obtener_servicio_calendar()

        ahora = datetime.datetime.now(datetime.timezone.utc)
        limite = ahora + datetime.timedelta(days=30)

        # q= es el parámetro de búsqueda de texto de la API.
        resultado = servicio.events().list(
            calendarId="primary",
            timeMin=ahora.isoformat(),
            timeMax=limite.isoformat(),
            singleEvents=True,
            orderBy="startTime",
            q=query,
            maxResults=10
        ).execute()

        eventos = resultado.get("items", [])

        if not eventos:
            return f"No encontré eventos que coincidan con '{query}'."

        lineas = []
        for evento in eventos:
            inicio = evento["start"].get("dateTime", evento["start"].get("date", ""))
            titulo = evento.get("summary", "Sin título")

            if "T" in inicio:
                dt = datetime.datetime.fromisoformat(inicio)
                lineas.append(f"{dt.strftime('%d/%m a las %I:%M %p')}: {titulo}")
            else:
                dt = datetime.date.fromisoformat(inicio)
                lineas.append(f"{dt.strftime('%d/%m')}: {titulo}")

        return f"Encontré {len(eventos)} evento(s). " + ". ".join(lineas) + "."

    except FileNotFoundError as error:
        return str(error)
    except Exception as error:
        return f"Error al buscar eventos: {error}"


# --- Prueba directa ---
if __name__ == "__main__":
    print("=== Prueba de Google Calendar ===\n")

    # La primera vez abrirá tu navegador para autorizar.
    print("1. Eventos de hoy:")
    print(f"   {ver_eventos_hoy()}\n")

    print("2. Eventos de mañana:")
    print(f"   {ver_eventos_manana()}\n")

    print("3. Próximos 7 días:")
    print(f"   {proximos_eventos(7)}\n")

    print("4. Creando evento de prueba...")
    manana = (datetime.date.today() + datetime.timedelta(days=1)).isoformat()
    print(f"   {crear_evento('Prueba Eli', manana, '10:00', 30)}\n")

    print("5. Buscando 'Prueba':")
    print(f"   {buscar_evento('Prueba')}\n")
