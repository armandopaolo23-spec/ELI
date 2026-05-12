"""Detección de fin de habla con Silero VAD (ONNX) en tiempo real.

Reemplaza la lógica manual de detección de silencio que vivía en
``escuchar.py`` (umbral de volumen + contador de bloques silenciosos).
Silero VAD usa un modelo ONNX entrenado para detectar voz humana y
devuelve eventos ``start`` / ``end`` con baja latencia (~150-250ms tras
el último fonema), independiente del ruido de fondo.

Diseño:
  - Stream sounddevice propio a 16kHz, blocksize 512 (~32ms/chunk).
    Silero VAD requiere exactamente ese tamaño de bloque a esa SR.
  - Cola interna ``_q`` re-exportada por ``escuchar.py`` para que el
    drain post-wake-word en main.py siga funcionando sin cambios.
  - Prebuffer circular de ``VAD_SPEECH_PAD_MS`` para no perder los
    primeros fonemas cuando Silero detecta ``start`` (siempre llega
    un par de chunks tarde).
  - ``VADIterator`` mantiene estado entre llamadas; se resetea al
    inicio de cada ``detectar_audio()``.
"""

from __future__ import annotations

import collections
import queue
import threading
import time
from typing import Any

import numpy as np
import sounddevice as sd

import config as cfg
from logger import get_logger, timing_decorator

log = get_logger(__name__)

# Silero VAD requiere chunks de exactamente 512 samples a 16kHz.
SAMPLERATE = 16000
BLOCKSIZE = 512  # ~32ms a 16kHz


_modelo: Any | None = None
_vad_iterator: Any | None = None
_stream: sd.InputStream | None = None
_q: queue.Queue = queue.Queue()
_lock = threading.Lock()


def _callback(indata: Any, frames: int, time_info: Any, status: Any) -> None:
    _q.put(indata.copy())


def precarga() -> None:
    """Carga el modelo Silero VAD (idempotente).

    Pensado para invocarse desde un hilo en el arranque, en paralelo
    con la calibración del mic, la precarga de Ollama y la de Whisper.
    """
    global _modelo, _vad_iterator
    if _modelo is not None:
        return

    with _lock:
        if _modelo is not None:
            return

        log.info("🔧 Cargando Silero VAD (ONNX)...")
        try:
            from silero_vad import load_silero_vad, VADIterator
        except ImportError as error:
            log.error("silero-vad no instalado: %s", error)
            raise

        _modelo = load_silero_vad(onnx=True)
        _vad_iterator = VADIterator(
            _modelo,
            threshold=cfg.VAD_THRESHOLD,
            sampling_rate=SAMPLERATE,
            min_silence_duration_ms=cfg.VAD_MIN_SILENCE_MS,
            speech_pad_ms=cfg.VAD_SPEECH_PAD_MS,
        )
        log.info("✅ Silero VAD listo.")


def calibrar_stream() -> None:
    """Abre el InputStream a 16kHz si no está abierto (idempotente)."""
    global _stream
    if _stream is not None:
        return
    log.info("🔧 Iniciando micrófono a 16kHz...")
    _stream = sd.InputStream(
        samplerate=SAMPLERATE,
        channels=1,
        dtype="float32",
        latency="low",
        blocksize=BLOCKSIZE,
        callback=_callback,
    )
    _stream.start()
    time.sleep(cfg.MIC_WARMUP_SECONDS)
    while not _q.empty():
        _q.get()
    log.info("✅ Micrófono listo.")


@timing_decorator
def detectar_audio() -> np.ndarray | None:
    """Captura audio hasta que Silero VAD detecte fin de habla.

    Retorna:
        np.ndarray float32 mono a 16kHz con el habla completa, o
        ``None`` si pasaron ``VAD_TIMEOUT_INICIO`` segundos sin
        detectar voz.
    """
    if _modelo is None:
        precarga()
    if _stream is None:
        calibrar_stream()

    # Drenar audio residual del buffer antes de empezar.
    while not _q.empty():
        _q.get()

    _vad_iterator.reset_states()

    # Prebuffer: chunks previos a la detección de "start" que se
    # anteponen al audio final, para no recortar fonemas iniciales.
    chunks_pad = max(1, int(cfg.VAD_SPEECH_PAD_MS / 1000.0 * SAMPLERATE / BLOCKSIZE))
    prebuffer: collections.deque = collections.deque(maxlen=chunks_pad)

    bloques: list[np.ndarray] = []
    hablando = False
    t_inicio = time.time()
    t_voz_detectada: float | None = None

    while True:
        bloque = _q.get()
        bloque_1d = bloque.flatten().astype(np.float32)
        if len(bloque_1d) != BLOCKSIZE:
            # sounddevice puede entregar un último chunk corto al
            # cerrar; lo ignoramos porque Silero exige tamaño fijo.
            continue

        if hablando:
            bloques.append(bloque_1d)
        else:
            prebuffer.append(bloque_1d)
            if time.time() - t_inicio > cfg.VAD_TIMEOUT_INICIO:
                return None

        evento = _vad_iterator(bloque_1d)
        if evento is None:
            continue

        if "start" in evento and not hablando:
            hablando = True
            t_voz_detectada = time.time()
            log.debug("🎤 Voz detectada")
            # Backfill: arrastrar los chunks del prebuffer antes
            # del chunk actual (que ya está en `prebuffer`).
            bloques.extend(prebuffer)
            prebuffer.clear()
        elif "end" in evento and hablando:
            duracion = time.time() - (t_voz_detectada or t_inicio)
            log.info("✅ Fin de habla (%.1fs)", duracion)
            break

    if not bloques:
        return None
    return np.concatenate(bloques).astype(np.float32)
