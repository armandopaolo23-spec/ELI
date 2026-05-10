"""Shim de retrocompatibilidad: ``pc_control`` se mudó a ``comandos/``.

El contenido original (945 líneas) fue dividido por dominio en
``comandos/{apps,sistema,tiempo,web,spotify,gmail,calendario,ingenieria}.py``.
Este archivo solo re-exporta la superficie pública para que cualquier
código que aún haga ``from pc_control import ...`` siga funcionando.
"""

from __future__ import annotations

from comandos import (
    CALENDAR_DISPONIBLE,
    CARPETA_PROYECTOS,
    DISPATCH,
    GMAIL_DISPONIBLE,
    SPOTIFY_DISPONIBLE,
    _consultar_clima,
    configurar_voz,
    ejecutar_comando,
)

__all__ = [
    "CALENDAR_DISPONIBLE",
    "CARPETA_PROYECTOS",
    "DISPATCH",
    "GMAIL_DISPONIBLE",
    "SPOTIFY_DISPONIBLE",
    "_consultar_clima",
    "configurar_voz",
    "ejecutar_comando",
]
