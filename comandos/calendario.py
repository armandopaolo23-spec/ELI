"""Google Calendar: agenda, creación y búsqueda de eventos."""

from __future__ import annotations

from typing import Any

from logger import get_logger

log = get_logger(__name__)


try:
    import google_calendar
    DISPONIBLE = True
except Exception as error:
    DISPONIBLE = False
    log.warning("Google Calendar no disponible: %s", error)


def _check() -> str | None:
    if not DISPONIBLE:
        return "Google Calendar no está configurado. Revisa credentials.json."
    return None


def _hoy(params: dict[str, Any]) -> str:
    error = _check()
    if error:
        return error
    return google_calendar.ver_eventos_hoy()


def _manana(params: dict[str, Any]) -> str:
    error = _check()
    if error:
        return error
    return google_calendar.ver_eventos_manana()


def _semana(params: dict[str, Any]) -> str:
    error = _check()
    if error:
        return error
    dias = params.get("dias", 7)
    try:
        dias = int(dias)
    except (ValueError, TypeError):
        dias = 7
    return google_calendar.proximos_eventos(dias)


def _crear_evento(params: dict[str, Any]) -> str:
    """Crea un evento de calendario.

    Ollama envía::

        {"titulo": "...", "fecha": "YYYY-MM-DD",
         "hora": "HH:MM", "duracion": 60}
    """
    error = _check()
    if error:
        return error

    titulo = params.get("titulo", "")
    fecha = params.get("fecha", "")
    hora = params.get("hora", "")
    duracion = params.get("duracion", 60)

    if not titulo:
        return "¿Cómo se llama el evento?"
    if not fecha:
        return "¿Qué día es el evento? Necesito la fecha."
    if not hora:
        return "¿A qué hora es el evento?"

    try:
        duracion = int(duracion)
    except (ValueError, TypeError):
        duracion = 60

    return google_calendar.crear_evento(titulo, fecha, hora, duracion)


def _buscar_evento(params: dict[str, Any]) -> str:
    error = _check()
    if error:
        return error
    busqueda = params.get("busqueda", "")
    if not busqueda:
        return "¿Qué evento quieres buscar?"
    return google_calendar.buscar_evento(busqueda)


DISPATCH: dict[str, Any] = {
    "calendario_hoy":           _hoy,
    "calendario_manana":        _manana,
    "calendario_semana":        _semana,
    "crear_evento_calendario":  _crear_evento,
    "buscar_evento_calendario": _buscar_evento,
}
