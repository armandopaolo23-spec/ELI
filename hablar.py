# ============================================================
# hablar.py — Voz de Eli con pipeline por oraciones (Piper local)
#
# ANTES: edge-tts contra Microsoft Azure. ~500-1000ms por oración
#   solo por el roundtrip de red. Requería internet.
#
# AHORA: Piper ONNX local. ~80-150ms por oración corta, sin red.
#
# Pipeline por oraciones: mientras se reproduce la oración N, un hilo
# productor ya está sintetizando la oración N+1. Con Piper local la
# ganancia por pipelining es menor (la síntesis ya es <150ms), pero
# sigue ayudando en respuestas largas y mantiene compat con el caller.
# ============================================================

from __future__ import annotations

import queue
import re
import threading
from typing import Any

import sounddevice as sd

import config as cfg
import piper_tts
from logger import get_logger

log = get_logger(__name__)

_MIN_LARGO_FRAGMENTO = cfg.TTS_MIN_FRAGMENTO
_BUFFER_ORACIONES = cfg.TTS_BUFFER_ORACIONES

# Sentinel que marca el fin del stream de audio en la cola.
_FIN_AUDIO = object()


def hablar(texto: str) -> None:
    """Convierte texto a voz y lo reproduce.

    Si el texto tiene varias oraciones, las pipeliniza: sintetiza
    la siguiente mientras la actual se reproduce.
    """
    if not texto or not texto.strip():
        return

    oraciones = _dividir_oraciones(texto)
    if not oraciones:
        return

    # Una sola oración: ruta simple, sin overhead de hilo+cola.
    if len(oraciones) == 1:
        _reproducir_una(oraciones[0])
        return

    # Pipeline multi-oración.
    cola: queue.Queue = queue.Queue(maxsize=_BUFFER_ORACIONES)
    hilo = threading.Thread(
        target=_productor, args=(oraciones, cola), daemon=True
    )
    hilo.start()

    while True:
        item = cola.get()
        if item is _FIN_AUDIO:
            break
        datos, frecuencia = item
        sd.play(datos, frecuencia)
        sd.wait()

    hilo.join(timeout=1.0)


def _dividir_oraciones(texto: str) -> list[str]:
    """Divide texto en oraciones, fusionando fragmentos muy cortos."""
    partes = re.split(r"(?<=[.!?…])\s+", texto.strip())
    partes = [p.strip() for p in partes if p.strip()]

    if not partes:
        return []

    fusionadas = []
    acumulado = ""
    for parte in partes:
        acumulado = f"{acumulado} {parte}".strip() if acumulado else parte
        if len(acumulado) >= _MIN_LARGO_FRAGMENTO:
            fusionadas.append(acumulado)
            acumulado = ""

    # Si quedó un resto corto, pegarlo al último fragmento (o usarlo solo).
    if acumulado:
        if fusionadas:
            fusionadas[-1] = f"{fusionadas[-1]} {acumulado}"
        else:
            fusionadas.append(acumulado)

    return fusionadas


def _productor(oraciones: list[str], cola: queue.Queue) -> None:
    """Sintetiza cada oración y la pone en la cola en orden."""
    try:
        for oracion in oraciones:
            audio = _sintetizar(oracion)
            if audio is not None:
                cola.put(audio)
    except Exception as error:
        log.warning("Productor TTS falló: %s", error, exc_info=True)
    finally:
        cola.put(_FIN_AUDIO)


def _reproducir_una(texto: str) -> None:
    """Camino sin pipeline: una sola oración."""
    try:
        audio = _sintetizar(texto)
    except Exception:
        log.warning("TTS falló para texto de %d caracteres", len(texto), exc_info=True)
        return
    if audio is None:
        return
    datos, frecuencia = audio
    sd.play(datos, frecuencia)
    sd.wait()


def _sintetizar(texto: str) -> tuple[Any, int] | None:
    """Sintetiza una oración con Piper local.

    Retorna ``(datos, frecuencia)`` o ``None`` si no se generó audio.
    """
    return piper_tts.sintetizar(texto)


# --- Prueba directa ---
if __name__ == "__main__":
    import time

    piper_tts.precarga()
    print("=== Prueba del pipeline con Piper local ===\n")

    inicio = time.time()
    hablar("Sistemas en línea. Listo para ayudarte. Los parámetros son aceptables.")
    t1 = time.time() - inicio

    inicio = time.time()
    hablar("Una sola oración corta.")
    t2 = time.time() - inicio

    print(f"\nMulti-oración: {t1:.2f}s | Una oración: {t2:.2f}s")
