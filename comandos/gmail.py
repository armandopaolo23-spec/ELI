"""Comandos de Gmail (cuenta, lectura, búsqueda, envío)."""

from __future__ import annotations

from typing import Any

from logger import get_logger

log = get_logger(__name__)


try:
    import gmail as _gmail_mod
    DISPONIBLE = True
except Exception as error:
    DISPONIBLE = False
    log.warning("Gmail no disponible: %s", error)


def _check() -> str | None:
    if not DISPONIBLE:
        return "Gmail no está configurado."
    return None


def _no_leidos(params: dict[str, Any]) -> str:
    error = _check()
    if error:
        return error
    return _gmail_mod.contar_no_leidos()


def _recientes(params: dict[str, Any]) -> str:
    error = _check()
    if error:
        return error
    cantidad = params.get("cantidad", 5)
    try:
        cantidad = int(cantidad)
    except (ValueError, TypeError):
        cantidad = 5
    return _gmail_mod.leer_emails_recientes(cantidad)


def _importantes(params: dict[str, Any]) -> str:
    error = _check()
    if error:
        return error
    return _gmail_mod.leer_email_importante()


def _buscar(params: dict[str, Any]) -> str:
    error = _check()
    if error:
        return error
    busqueda = params.get("busqueda", "")
    if not busqueda:
        return "¿Qué email quieres buscar?"
    return _gmail_mod.buscar_email(busqueda)


def _enviar(params: dict[str, Any]) -> str:
    error = _check()
    if error:
        return error
    destinatario = params.get("destinatario", "")
    asunto = params.get("asunto", "")
    cuerpo = params.get("cuerpo", "")
    if not destinatario:
        return "¿A quién quieres enviar el email? Necesito la dirección."
    if not asunto:
        asunto = "Mensaje de Eli"
    if not cuerpo:
        return "¿Qué quieres que diga el email?"
    return _gmail_mod.enviar_email(destinatario, asunto, cuerpo)


DISPATCH: dict[str, Any] = {
    "gmail_no_leidos":   _no_leidos,
    "gmail_recientes":   _recientes,
    "gmail_importantes": _importantes,
    "gmail_buscar":      _buscar,
    "gmail_enviar":      _enviar,
}
