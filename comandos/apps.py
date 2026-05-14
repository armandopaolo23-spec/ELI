"""Apps de uso general (Chrome, Notepad, Calc, Office, Explorer).

Cada handler retorna un mensaje para que Eli lo diga. La lógica de
"cómo abrir cada app en cada SO" vive en ``os_compat``; aquí solo
elegimos el nombre lógico y armamos el mensaje.
"""

from __future__ import annotations

import time
from typing import Any

import pyautogui

import os_compat
from logger import get_logger

log = get_logger(__name__)


def _abrir_app_simple(
    nombre_logico: str, mensaje_ok: str, mensaje_falla: str
) -> str:
    """Invoca ``os_compat.abrir_app`` y devuelve el mensaje correspondiente."""
    if os_compat.abrir_app(nombre_logico):
        return mensaje_ok
    return mensaje_falla


def _abrir_chrome(params: dict[str, Any]) -> str:
    return _abrir_app_simple(
        "chrome", "Abriendo Chrome.",
        "No encontré Chrome instalado.",
    )


def _abrir_notepad(params: dict[str, Any]) -> str:
    return _abrir_app_simple(
        "notepad", "Abriendo el editor de texto.",
        "No encontré un editor de texto instalado.",
    )


def _abrir_calculadora(params: dict[str, Any]) -> str:
    return _abrir_app_simple(
        "calculadora", "Abriendo la calculadora.",
        "No encontré una calculadora instalada.",
    )


def _abrir_explorador(params: dict[str, Any]) -> str:
    return _abrir_app_simple(
        "explorador", "Abriendo el explorador de archivos.",
        "No pude abrir el explorador.",
    )


def _abrir_configuracion(params: dict[str, Any]) -> str:
    return _abrir_app_simple(
        "configuracion", "Abriendo la configuración.",
        "No encontré la configuración del sistema.",
    )


def _abrir_word(params: dict[str, Any]) -> str:
    return _abrir_app_simple(
        "word", "Abriendo Word.",
        "No encontré Word ni LibreOffice Writer.",
    )


def _abrir_excel(params: dict[str, Any]) -> str:
    return _abrir_app_simple(
        "excel", "Abriendo Excel.",
        "No encontré Excel ni LibreOffice Calc.",
    )


def _abrir_powerpoint(params: dict[str, Any]) -> str:
    return _abrir_app_simple(
        "powerpoint", "Abriendo PowerPoint.",
        "No encontré PowerPoint ni LibreOffice Impress.",
    )


def _abrir_terminal(params: dict[str, Any]) -> str:
    return _abrir_app_simple(
        "terminal", "Abriendo la terminal.",
        "No encontré una terminal instalada.",
    )


def _abrir_vscode(params: dict[str, Any]) -> str:
    return _abrir_app_simple(
        "vscode", "Abriendo Visual Studio Code.",
        "No encontré Visual Studio Code instalado.",
    )


def _calculadora_cientifica(params: dict[str, Any]) -> str:
    """Abre la calculadora; en Windows manda Alt+2 para modo científico.

    En Linux no hay shortcut universal, así que solo abre la calculadora.
    """
    if not os_compat.abrir_app("calculadora"):
        return "No encontré una calculadora instalada."

    if os_compat.IS_WINDOWS:
        time.sleep(1)
        pyautogui.hotkey("alt", "2")
        return "Abriendo calculadora científica."
    return "Abriendo calculadora."


DISPATCH: dict[str, Any] = {
    "abrir_chrome":           _abrir_chrome,
    "abrir_notepad":          _abrir_notepad,
    "abrir_calculadora":      _abrir_calculadora,
    "abrir_explorador":       _abrir_explorador,
    "abrir_configuracion":    _abrir_configuracion,
    "abrir_word":             _abrir_word,
    "abrir_excel":            _abrir_excel,
    "abrir_powerpoint":       _abrir_powerpoint,
    "calculadora_cientifica": _calculadora_cientifica,
    "abrir_terminal":         _abrir_terminal,
    "abrir_vscode":           _abrir_vscode,
}
