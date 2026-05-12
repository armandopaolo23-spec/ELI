"""STT local con faster-whisper.

Sustituye al combo SpeechRecognition+Google que usaba ``escuchar.py``.
Whisper corre en GPU (CUDA) con ``compute_type=int8_float16`` para
balance entre VRAM y velocidad.

Patrón singleton: el modelo se carga una sola vez. ``precarga()`` se
llama desde ``main.py`` en paralelo con la calibración del micrófono y
la precarga de Ollama. ``transcribir()`` reutiliza la instancia.

El audio que recibe ``transcribir()`` debe ser:
  - ``numpy.ndarray`` 1-D
  - ``dtype=float32``
  - 16000 Hz, mono
  - normalizado entre -1.0 y 1.0

El downsample de 44.1kHz a 16kHz lo sigue haciendo ``escuchar.py`` con
``scipy.signal.resample_poly``; aquí solo asumimos audio limpio.
"""

from __future__ import annotations

import threading
from typing import Any

import numpy as np

import config as cfg
from logger import get_logger, timing_decorator

log = get_logger(__name__)


_modelo: Any | None = None
_lock = threading.Lock()


def precarga() -> None:
    """Carga el modelo en GPU (idempotente).

    Pensado para invocarse desde un hilo en el arranque, en paralelo
    con la calibración del mic y la precarga del LLM.
    """
    global _modelo
    if _modelo is not None:
        return

    with _lock:
        if _modelo is not None:
            return

        log.info(
            "🔧 Cargando Whisper (%s, device=%s, compute=%s)...",
            cfg.WHISPER_MODELO, cfg.WHISPER_DEVICE, cfg.WHISPER_COMPUTE_TYPE,
        )
        try:
            from faster_whisper import WhisperModel
        except ImportError as error:
            log.error("faster-whisper no instalado: %s", error)
            raise

        _modelo = WhisperModel(
            cfg.WHISPER_MODELO,
            device=cfg.WHISPER_DEVICE,
            compute_type=cfg.WHISPER_COMPUTE_TYPE,
        )
        log.info("✅ Whisper listo.")


@timing_decorator
def transcribir(audio_float32_16khz: np.ndarray) -> str:
    """Transcribe audio a texto con Whisper.

    Args:
        audio_float32_16khz: array 1-D float32 a 16000 Hz, mono.

    Retorna:
        str: texto transcrito en minúsculas, o "" si no se entendió.
    """
    if _modelo is None:
        precarga()

    # faster-whisper acepta np.ndarray directo, evitando archivos
    # temporales o serialización a WAV.
    segments, _info = _modelo.transcribe(
        audio_float32_16khz,
        language=cfg.WHISPER_IDIOMA,
        beam_size=cfg.WHISPER_BEAM_SIZE,
        vad_filter=False,                  # VAD ya se hizo en escuchar.py.
        condition_on_previous_text=False,  # Sin contexto cross-turno.
    )
    texto = " ".join(s.text for s in segments).strip()
    return texto.lower()
