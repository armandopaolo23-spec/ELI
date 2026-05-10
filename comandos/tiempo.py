"""Fecha, hora, clima y temporizador.

Este submódulo también es dueño del estado del temporizador y de la
función ``configurar_voz`` que main.py invoca al arrancar para inyectar
``hablar()``. El temporizador necesita esa función para anunciar al
usuario que terminó.
"""

from __future__ import annotations

import datetime
import threading
import urllib.parse
from typing import Any, Callable

import requests

from logger import get_logger

log = get_logger(__name__)


# --- Estado del temporizador ---
_temporizador_activo: threading.Timer | None = None
_funcion_hablar: Callable[[str], None] | None = None


def configurar_voz(funcion_hablar: Callable[[str], None]) -> None:
    """Inyecta ``hablar()`` para que el callback del temporizador la use."""
    global _funcion_hablar
    _funcion_hablar = funcion_hablar


# ============================================================
# HORA / FECHA
# ============================================================

def _decir_hora(params: dict[str, Any]) -> str:
    ahora = datetime.datetime.now()
    return f"Son las {ahora.strftime('%I:%M %p')}."


def _decir_fecha(params: dict[str, Any]) -> str:
    ahora = datetime.datetime.now()
    dias = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"]
    meses = [
        "enero", "febrero", "marzo", "abril", "mayo", "junio",
        "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre",
    ]
    return (
        f"Hoy es {dias[ahora.weekday()]} {ahora.day} "
        f"de {meses[ahora.month - 1]} de {ahora.year}."
    )


# ============================================================
# CLIMA
# ============================================================

def _consultar_clima(params: dict[str, Any]) -> str:
    """Consulta wttr.in para una ciudad."""
    ciudad = params.get("ciudad", "")
    if not ciudad:
        return "No entendí de qué ciudad quieres saber el clima."
    try:
        url = (
            f"https://wttr.in/{urllib.parse.quote(ciudad)}"
            f"?format=%C,+%t,+humedad+%h,+viento+%w&lang=es"
        )
        resp = requests.get(url, timeout=5)
        if resp.status_code == 200 and "Unknown" not in resp.text:
            return f"El clima en {ciudad}: {resp.text.strip()}."
        return f"No encontré información del clima para {ciudad}."
    except requests.ConnectionError:
        return "No pude consultar el clima. Verifica tu conexión."
    except Exception:
        return "Hubo un error al consultar el clima."


# ============================================================
# TEMPORIZADOR
# ============================================================

def _poner_temporizador(params: dict[str, Any]) -> str:
    global _temporizador_activo

    cantidad = params.get("cantidad", 0)
    unidad = params.get("unidad", "minutos").lower()
    try:
        cantidad = int(cantidad)
    except (ValueError, TypeError):
        return "No entendí la cantidad del temporizador."
    if cantidad <= 0:
        return "La cantidad debe ser mayor a cero."

    if "segundo" in unidad:
        segundos = cantidad
    elif "hora" in unidad:
        segundos = cantidad * 3600
    else:
        segundos = cantidad * 60

    unidad_limpia = unidad.rstrip("s")
    texto_tiempo = f"{cantidad} {unidad_limpia}" + ("s" if cantidad != 1 else "")

    if _temporizador_activo and _temporizador_activo.is_alive():
        _temporizador_activo.cancel()
    _temporizador_activo = threading.Timer(
        segundos, _temporizador_terminado, args=[texto_tiempo]
    )
    _temporizador_activo.daemon = True
    _temporizador_activo.start()
    return f"Temporizador de {texto_tiempo} iniciado."


def _cancelar_temporizador(params: dict[str, Any]) -> str:
    global _temporizador_activo
    if _temporizador_activo and _temporizador_activo.is_alive():
        _temporizador_activo.cancel()
        _temporizador_activo = None
        return "Temporizador cancelado."
    return "No hay ningún temporizador activo."


def _temporizador_terminado(texto_tiempo: str) -> None:
    mensaje = f"¡Tiempo! El temporizador de {texto_tiempo} ha terminado."
    log.info("⏰ %s", mensaje)
    if _funcion_hablar:
        _funcion_hablar(mensaje)


DISPATCH: dict[str, Any] = {
    # Alias históricos: "dejar_hora" y "decir_hora_actual" estaban en
    # el DISPATCH original de pc_control. Se preservan para no romper
    # outputs de Ollama que aún los emitan.
    "dejar_hora":            _decir_hora,
    "decir_hora_actual":     _decir_hora,
    "decir_fecha":           _decir_fecha,
    "consultar_clima":       _consultar_clima,
    "poner_temporizador":    _poner_temporizador,
    "cancelar_temporizador": _cancelar_temporizador,
}
