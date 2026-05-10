# ============================================================
# hablar.py — Voz de Eli con pipeline por oraciones
#
# ANTES: edge-tts genera todo el MP3 → decodifica → reproduce.
#   Para una respuesta de 3 oraciones, el usuario espera que se
#   sintetice todo el texto antes de oír la primera palabra.
#
# AHORA: dividimos por oraciones y solapamos síntesis con playback.
#   Mientras se reproduce la oración N, un hilo productor ya está
#   sintetizando la oración N+1 contra el servidor de Microsoft.
#
# Ganancia:
#   - Time-to-first-audio: ~0.3s en vez de ~0.6s (síntesis de
#     una oración corta vs texto completo).
#   - Latencia total: −0.3 a −0.8s en respuestas multi-oración,
#     porque el roundtrip de red de la oración N+1 se solapa
#     con el playback de la N.
# ============================================================

from __future__ import annotations

import asyncio
import io
import queue
import re
import threading
from typing import Any

import edge_tts
import sounddevice as sd
import soundfile as sf

import config as cfg
from logger import get_logger

log = get_logger(__name__)

VOZ = cfg.VOZ
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
        try:
            asyncio.run(_reproducir_una(oraciones[0]))
        except Exception:
            log.warning("TTS falló para texto de %d caracteres", len(texto), exc_info=True)
        return

    # Pipeline multi-oración.
    cola = queue.Queue(maxsize=_BUFFER_ORACIONES)
    hilo = threading.Thread(
        target=_correr_productor, args=(oraciones, cola), daemon=True
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


def _correr_productor(oraciones: list[str], cola: queue.Queue) -> None:
    """Wrapper que lanza el productor async y captura excepciones."""
    try:
        asyncio.run(_productor(oraciones, cola))
    except Exception as error:
        log.warning("Productor TTS falló: %s", error, exc_info=True)
        try:
            cola.put_nowait(_FIN_AUDIO)
        except queue.Full:
            pass


async def _productor(oraciones: list[str], cola: queue.Queue) -> None:
    """Sintetiza cada oración y la pone en la cola en orden."""
    for oracion in oraciones:
        audio = await _sintetizar(oracion)
        if audio is not None:
            cola.put(audio)
    cola.put(_FIN_AUDIO)


async def _reproducir_una(texto: str) -> None:
    """Camino sin pipeline: una sola oración."""
    audio = await _sintetizar(texto)
    if audio is None:
        return
    datos, frecuencia = audio
    sd.play(datos, frecuencia)
    sd.wait()


async def _sintetizar(texto: str) -> tuple[Any, int] | None:
    """Genera audio MP3 con edge-tts y lo decodifica a numpy.

    Retorna ``(datos, frecuencia)`` o ``None`` si no se generó audio.
    El primer elemento es ``np.ndarray``; lo dejamos como ``Any`` para
    no atar este módulo a numpy en su firma.
    """
    buffer = io.BytesIO()
    comunicador = edge_tts.Communicate(texto, VOZ)
    async for chunk in comunicador.stream():
        if chunk["type"] == "audio":
            buffer.write(chunk["data"])

    if buffer.tell() == 0:
        return None

    buffer.seek(0)
    datos, frecuencia = sf.read(buffer)
    return datos, frecuencia


# --- Prueba directa ---
if __name__ == "__main__":
    import time

    print("=== Prueba del pipeline por oraciones ===\n")

    inicio = time.time()
    hablar("Sistemas en línea. Listo para ayudarte. Los parámetros son aceptables.")
    t1 = time.time() - inicio

    inicio = time.time()
    hablar("Una sola oración corta.")
    t2 = time.time() - inicio

    print(f"\nMulti-oración: {t1:.2f}s | Una oración: {t2:.2f}s")
