"""Comandos disponibles para Eli.

Reemplaza el monolito ``pc_control.py`` (945 líneas) por submódulos
por dominio. Cada submódulo expone:

- Funciones handler con firma uniforme ``(params: dict) -> str | None``.
- Una constante ``DISPATCH`` que mapea nombres de comandos a handlers.

Este ``__init__`` agrega los DISPATCH de cada submódulo en uno solo y
re-exporta las funciones que ``main.py`` y ``rutinas.py`` necesitan.

El archivo ``pc_control.py`` queda como shim de retrocompatibilidad
que re-exporta desde aquí.
"""

from __future__ import annotations

from typing import Any

from blackboard_commands import abrir_curso, listar_mis_cursos
from logger import get_logger

from . import apps, calendario, gmail, ingenieria, sistema, spotify, tiempo, web
from .ingenieria import CARPETA_PROYECTOS
from .tiempo import _consultar_clima, configurar_voz

log = get_logger(__name__)


# Flags de disponibilidad re-exportados desde cada submódulo de
# integración. Útiles para diagnóstico y para el shim retrocompatible.
SPOTIFY_DISPONIBLE = spotify.DISPONIBLE
CALENDAR_DISPONIBLE = calendario.DISPONIBLE
GMAIL_DISPONIBLE = gmail.DISPONIBLE


def _abrir_curso(params: dict[str, Any]) -> str | None:
    # Estructura legacy del comando: ``parametros`` viene anidado.
    nested = params.get("parametros", {})
    return abrir_curso(nested.get("nombre_curso", ""))


DISPATCH: dict[str, Any] = {
    **apps.DISPATCH,
    **sistema.DISPATCH,
    **tiempo.DISPATCH,
    **web.DISPATCH,
    **spotify.DISPATCH,
    **gmail.DISPATCH,
    **calendario.DISPATCH,
    **ingenieria.DISPATCH,
    "listar_cursos": lambda p: listar_mis_cursos(),
    "abrir_curso":   _abrir_curso,
}


def ejecutar_comando(nombre: str, parametros: dict[str, Any]) -> str | None:
    """Ejecuta un comando del PC por su nombre.

    Args:
        nombre: Nombre del comando emitido por Ollama.
        parametros: Parámetros extraídos por Ollama.

    Retorna:
        Texto para que Eli diga, o ``None`` si el comando no existe.
    """
    funcion = DISPATCH.get(nombre)
    if funcion is None:
        return None
    return funcion(parametros)


__all__ = [
    "DISPATCH",
    "SPOTIFY_DISPONIBLE",
    "CALENDAR_DISPONIBLE",
    "GMAIL_DISPONIBLE",
    "CARPETA_PROYECTOS",
    "ejecutar_comando",
    "configurar_voz",
    "_consultar_clima",
]
