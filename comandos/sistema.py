"""Acciones del sistema: volumen, captura, lock, apagado, papelera, tema, batería."""

from __future__ import annotations

import datetime
from typing import Any

import psutil
import pyautogui

import os_compat
from logger import get_logger

log = get_logger(__name__)


# ============================================================
# VOLUMEN
# ============================================================

def _subir_volumen(params: dict[str, Any]) -> str:
    for _ in range(5):
        pyautogui.press("volumeup")
    return "Volumen subido."


def _bajar_volumen(params: dict[str, Any]) -> str:
    for _ in range(5):
        pyautogui.press("volumedown")
    return "Volumen bajado."


def _silenciar(params: dict[str, Any]) -> str:
    pyautogui.press("volumemute")
    return "Audio silenciado."


def _volumen_especifico(params: dict[str, Any]) -> str:
    porcentaje = params.get("porcentaje", 50)
    try:
        porcentaje = int(porcentaje)
    except (ValueError, TypeError):
        porcentaje = 50
    porcentaje = max(0, min(100, porcentaje))
    for _ in range(50):
        pyautogui.press("volumedown")
    for _ in range(porcentaje // 2):
        pyautogui.press("volumeup")
    return f"Volumen del sistema al {porcentaje}%."


# ============================================================
# PANTALLA
# ============================================================

def _captura_pantalla(params: dict[str, Any]) -> str:
    ahora = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    ruta = str(os_compat.DESKTOP / f"captura_{ahora}.png")
    pyautogui.screenshot(ruta)
    return "Captura guardada en el escritorio."


def _bloquear_pantalla(params: dict[str, Any]) -> str:
    if os_compat.bloquear_pantalla():
        return "Bloqueando la pantalla."
    return "No pude bloquear la pantalla."


# ============================================================
# APAGADO / PAPELERA / TEMA / BATERÍA
# ============================================================

def _apagar_pc(params: dict[str, Any]) -> str:
    if os_compat.apagar_pc(60):
        return "La computadora se apagará en 60 segundos. Di cancelar apagado para detenerlo."
    return "No pude programar el apagado."


def _cancelar_apagado(params: dict[str, Any]) -> str:
    if os_compat.cancelar_apagado():
        return "Apagado cancelado."
    return "No había un apagado programado o no pude cancelarlo."


def _vaciar_papelera(params: dict[str, Any]) -> str:
    if os_compat.vaciar_papelera():
        return "Papelera vaciada."
    return "No pude vaciar la papelera."


def _modo_oscuro(params: dict[str, Any]) -> str:
    nuevo_modo = os_compat.modo_oscuro_toggle()
    if nuevo_modo:
        return f"Modo {nuevo_modo} activado."
    return "No pude cambiar el tema del sistema."


def _bateria(params: dict[str, Any]) -> str:
    bateria = psutil.sensors_battery()
    if bateria is None:
        return "No detecté una batería."
    porcentaje = int(bateria.percent)
    cargando = " y cargando" if bateria.power_plugged else ""
    return f"La batería está al {porcentaje}%{cargando}."


DISPATCH: dict[str, Any] = {
    "subir_volumen":     _subir_volumen,
    "bajar_volumen":     _bajar_volumen,
    "silenciar":         _silenciar,
    "volumen_especifico": _volumen_especifico,
    "captura_pantalla":  _captura_pantalla,
    "bloquear_pantalla": _bloquear_pantalla,
    "apagar_pc":         _apagar_pc,
    "cancelar_apagado":  _cancelar_apagado,
    "vaciar_papelera":   _vaciar_papelera,
    "modo_oscuro":       _modo_oscuro,
    "bateria":           _bateria,
}
