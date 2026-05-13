"""TTS local con Piper (ONNX).

Sustituye al combo edge-tts (Microsoft Azure por red) que usaba
``hablar.py``. Piper corre 100% local: ~80-150ms para sintetizar una
oración corta vs los 500-1000ms del roundtrip a Azure.

Patrón singleton: el modelo se carga una sola vez. ``precarga()`` se
llama desde ``main.py`` en paralelo con el resto del bootstrap.
``sintetizar()`` reutiliza la instancia.

Output: ``(np.ndarray int16, sample_rate)`` listo para ``sd.play()``.
"""

from __future__ import annotations

import threading
from pathlib import Path
from typing import Any

import numpy as np

import config as cfg
from logger import get_logger, timing_decorator

log = get_logger(__name__)


_voz: Any | None = None
_lock = threading.Lock()


def precarga() -> None:
    """Carga el modelo Piper (idempotente).

    Pensado para invocarse desde un hilo en el arranque, en paralelo
    con la calibración del mic, Ollama, Whisper y Silero VAD.
    """
    global _voz
    if _voz is not None:
        return

    with _lock:
        if _voz is not None:
            return

        modelo = Path(cfg.PIPER_MODELO_PATH)
        log.info("🔧 Cargando Piper (%s)...", modelo.name)

        if not modelo.exists():
            raise FileNotFoundError(
                f"Modelo Piper no encontrado en {modelo}. "
                "Descárgalo desde https://huggingface.co/rhasspy/piper-voices "
                "o configura ELI_PIPER_MODELO_PATH."
            )

        try:
            from piper.voice import PiperVoice
        except ImportError as error:
            log.error("piper-tts no instalado: %s", error)
            raise

        _voz = PiperVoice.load(str(modelo))
        log.info("✅ Piper listo (sample_rate=%d).", _voz.config.sample_rate)


@timing_decorator
def sintetizar(texto: str) -> tuple[np.ndarray, int] | None:
    """Sintetiza texto a audio PCM int16.
    
    Args:
        texto: texto a sintetizar.
    Retorna:
        ``(np.ndarray int16, sample_rate)`` o ``None`` si no se generó
        audio (texto vacío, etc.).
    """
    if _voz is None:
        precarga()
    
    if not texto.strip():
        return None
    
    # Calcular parámetros de síntesis
    
    # synthesize() retorna Iterable[AudioChunk]
    # Cada AudioChunk tiene .audio (numpy array)
    chunks = []
    for chunk in _voz.synthesize(texto):
        chunks.append(chunk.audio_int16_array)
    
    if not chunks:
        return None
    
    # Concatenar todos los chunks
    audio_array = np.concatenate(chunks)
    
    return audio_array, _voz.config.sample_rate

