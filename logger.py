"""Logging centralizado para Eli.

Uso:
    from logger import get_logger
    log = get_logger(__name__)
    log.info("estado normal visible en consola")
    log.debug("detalle solo a archivo (timings, JSON crudo)")
    log.warning("problema recuperable")
    log.error("acción falló")

Configuración:
    - Consola: nivel INFO (legible, sin timestamps).
    - Archivo: logs/eli.log con rotación (1MB x 5), nivel DEBUG.
    - Variable entorno ELI_LOG_LEVEL=DEBUG fuerza DEBUG en consola.
"""

from __future__ import annotations

import collections
import functools
import logging
import logging.handlers
import os
import statistics
import sys
import time
from pathlib import Path

_LOG_DIR = Path(__file__).parent / "logs"
_LOG_FILE = _LOG_DIR / "eli.log"
_CONFIGURED = False


def configurar_logging(
    nivel_consola: int | None = None,
    nivel_archivo: int = logging.DEBUG,
) -> None:
    """Idempotente. Llamar una sola vez al inicio (main.py)."""
    global _CONFIGURED
    if _CONFIGURED:
        return

    if nivel_consola is None:
        env = os.environ.get("ELI_LOG_LEVEL", "").upper()
        nivel_consola = getattr(logging, env, logging.INFO) if env else logging.INFO

    _LOG_DIR.mkdir(exist_ok=True)

    raiz = logging.getLogger("eli")
    raiz.setLevel(logging.DEBUG)
    raiz.propagate = False

    if not raiz.handlers:
        consola = logging.StreamHandler(sys.stdout)
        consola.setLevel(nivel_consola)
        consola.setFormatter(logging.Formatter("%(message)s"))
        raiz.addHandler(consola)

        try:
            archivo = logging.handlers.RotatingFileHandler(
                _LOG_FILE, maxBytes=1_000_000, backupCount=5, encoding="utf-8"
            )
            archivo.setLevel(nivel_archivo)
            archivo.setFormatter(logging.Formatter(
                "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
            ))
            raiz.addHandler(archivo)
        except OSError as error:
            raiz.warning("No pude abrir el archivo de log: %s", error)

    _CONFIGURED = True


def get_logger(nombre: str) -> logging.Logger:
    """Retorna un logger anidado bajo 'eli.<nombre>'."""
    configurar_logging()
    if nombre == "__main__" or not nombre:
        nombre = "eli"
    elif not nombre.startswith("eli"):
        nombre = f"eli.{nombre}"
    return logging.getLogger(nombre)


def timing_decorator(func):
    """Mide latencia de la función y loguea percentiles p50/p95/p99 a DEBUG."""
    historial: collections.deque = collections.deque(maxlen=100)
    _log = get_logger("timing")

    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        t0 = time.perf_counter()
        resultado = func(*args, **kwargs)
        historial.append((time.perf_counter() - t0) * 1000)
        if len(historial) >= 2:
            data = sorted(historial)
            n = len(data)
            p50 = statistics.median(data)
            p95 = data[min(int(n * 0.95), n - 1)]
            p99 = data[min(int(n * 0.99), n - 1)]
            _log.debug(
                "⏱️ [%s] p50: %.0fms p95: %.0fms p99: %.0fms (n=%d)",
                func.__name__, p50, p95, p99, n,
            )
        return resultado

    wrapper._historial = historial
    return wrapper
