"""Búsquedas web y URLs (Google, YouTube, conversor de unidades)."""

from __future__ import annotations

import urllib.parse
import webbrowser
from typing import Any

from logger import get_logger

log = get_logger(__name__)


def _buscar_google(params: dict[str, Any]) -> str:
    busqueda = params.get("busqueda", "")
    if not busqueda:
        return "No entendí qué quieres buscar."
    webbrowser.open(
        f"https://www.google.com/search?q={urllib.parse.quote(busqueda)}"
    )
    return f"Buscando {busqueda} en Google."


def _abrir_youtube(params: dict[str, Any]) -> str:
    webbrowser.open("https://www.youtube.com")
    return "Abriendo YouTube."


def _buscar_youtube(params: dict[str, Any]) -> str:
    busqueda = params.get("busqueda", "")
    if not busqueda:
        return "No entendí qué quieres buscar."
    webbrowser.open(
        f"https://www.youtube.com/results?search_query={urllib.parse.quote(busqueda)}"
    )
    return f"Buscando {busqueda} en YouTube."


def _convertir_unidades(params: dict[str, Any]) -> str:
    """Abre el conversor de Google en el navegador."""
    tipo = params.get("tipo", "")
    if tipo:
        webbrowser.open(
            f"https://www.google.com/search?q=convertir+{urllib.parse.quote(tipo)}"
        )
        return f"Abriendo conversor de {tipo}."
    webbrowser.open("https://www.google.com/search?q=conversor+de+unidades")
    return "Abriendo conversor de unidades."


DISPATCH: dict[str, Any] = {
    "buscar_google":     _buscar_google,
    "abrir_youtube":     _abrir_youtube,
    "buscar_youtube":    _buscar_youtube,
    "convertir_unidades": _convertir_unidades,
}
