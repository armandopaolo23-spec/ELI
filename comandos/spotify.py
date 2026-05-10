"""Spotify: abrir cliente + controles vía API oficial (spotipy)."""

from __future__ import annotations

import time
from typing import Any

import os_compat
from logger import get_logger

log = get_logger(__name__)


# Import-time fallback: si spotipy no está instalado o sin credenciales,
# Eli sigue funcionando para todo lo demás.
try:
    import spotify_control
    DISPONIBLE = True
except Exception as error:
    DISPONIBLE = False
    log.warning("Spotify no disponible: %s. Los demás comandos siguen funcionando.", error)


def _check() -> str | None:
    if not DISPONIBLE:
        return "Spotify no está configurado. Revisa las credenciales en spotify_control.py."
    return None


def _abrir_spotify(params: dict[str, Any]) -> str:
    if os_compat.abrir_app("spotify"):
        time.sleep(3)  # Esperar a que Spotify inicie.
        return "Abriendo Spotify. Dame un momento para que cargue."
    return "No encontré Spotify instalado."


def _play(params: dict[str, Any]) -> str:
    error = _check()
    if error:
        return error
    return spotify_control.play()


def _pause(params: dict[str, Any]) -> str:
    error = _check()
    if error:
        return error
    return spotify_control.pause()


def _siguiente(params: dict[str, Any]) -> str:
    error = _check()
    if error:
        return error
    return spotify_control.siguiente()


def _anterior(params: dict[str, Any]) -> str:
    error = _check()
    if error:
        return error
    return spotify_control.anterior()


def _volumen(params: dict[str, Any]) -> str:
    error = _check()
    if error:
        return error
    porcentaje = params.get("porcentaje", 50)
    return spotify_control.volumen(porcentaje)


def _que_suena(params: dict[str, Any]) -> str:
    error = _check()
    if error:
        return error
    return spotify_control.que_suena()


def _buscar(params: dict[str, Any]) -> str:
    error = _check()
    if error:
        return error
    busqueda = params.get("busqueda", "")
    if not busqueda:
        return "No entendí qué canción quieres escuchar."
    return spotify_control.buscar_y_reproducir(busqueda)


def _playlist(params: dict[str, Any]) -> str:
    error = _check()
    if error:
        return error
    busqueda = params.get("busqueda", "")
    if not busqueda:
        return "¿Qué playlist quieres reproducir?"
    return spotify_control.buscar_y_reproducir_playlist(busqueda)


DISPATCH: dict[str, Any] = {
    "abrir_spotify":      _abrir_spotify,
    "spotify_play":       _play,
    "spotify_pause":      _pause,
    "spotify_siguiente":  _siguiente,
    "spotify_anterior":   _anterior,
    "spotify_volumen":    _volumen,
    "spotify_que_suena":  _que_suena,
    # "spotify_reproducir" es alias histórico de "spotify_buscar".
    "spotify_reproducir": _buscar,
    "spotify_buscar":     _buscar,
    "spotify_playlist":   _playlist,
}
