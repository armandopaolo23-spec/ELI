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
from logger import get_logger

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

    speaker = cfg.PIPER_SPEAKER if cfg.PIPER_SPEAKER >= 0 else None
    length_scale = 1.0 / cfg.PIPER_SPEED if cfg.PIPER_SPEED > 0 else 1.0

    audio_bytes = b"".join(_voz.synthesize_stream_raw(
        texto,
        speaker_id=speaker,
        length_scale=length_scale,
    ))
    if not audio_bytes:
        return None

    audio = np.frombuffer(audio_bytes, dtype=np.int16)
    return audio, _voz.config.sample_rate
