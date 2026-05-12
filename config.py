"""Configuración central de Eli.

Todos los parámetros tunables viven aquí. Cada uno tiene un default
sensato y puede sobreescribirse con una variable de entorno con el
prefijo ``ELI_*``.

Ejemplos::

    export ELI_MIC_UMBRAL=0.005          # micrófono más sensible
    export ELI_TIMEOUT_OLLAMA=120        # GPU lenta
    export ELI_VOZ=es-ES-AlvaroNeural    # cambiar voz de TTS
    export ELI_CIUDAD_CLIMA=Lima

Si una variable de entorno no se puede convertir al tipo esperado,
se loguea un warning y se usa el default.
"""

from __future__ import annotations

import os
from typing import Any

from logger import get_logger

log = get_logger(__name__)


def _env(nombre: str, default: Any, tipo: type = str) -> Any:
    """Lee ``ELI_<nombre>`` con conversión segura."""
    valor = os.environ.get(f"ELI_{nombre}")
    if valor is None:
        return default
    try:
        if tipo is bool:
            return valor.lower() in ("1", "true", "yes", "on")
        return tipo(valor)
    except (ValueError, TypeError):
        log.warning(
            "ELI_%s='%s' no es un %s válido; usando default %r",
            nombre, valor, tipo.__name__, default,
        )
        return default


# ============================================================
# LOOP PRINCIPAL
# ============================================================
TIMEOUT_INACTIVIDAD     = _env("TIMEOUT_INACTIVIDAD", 600, int)
MAX_FALLOS_CONSECUTIVOS = _env("MAX_FALLOS_CONSECUTIVOS", 3, int)
DELAY_ENTRE_COMANDOS    = _env("DELAY_ENTRE_COMANDOS", 1.5, float)

# ============================================================
# OLLAMA / CEREBRO
# ============================================================
TIMEOUT_OLLAMA          = _env("TIMEOUT_OLLAMA", 60, int)
TIMEOUT_OLLAMA_RESUMEN  = _env("TIMEOUT_OLLAMA_RESUMEN", 30, int)
TIMEOUT_OLLAMA_PERFIL   = _env("TIMEOUT_OLLAMA_PERFIL", 15, int)
TIMEOUT_OLLAMA_PRECARGA = _env("TIMEOUT_OLLAMA_PRECARGA", 30, int)
TIMEOUT_OLLAMA_PING     = _env("TIMEOUT_OLLAMA_PING", 2, int)
RECOVERY_INTERVAL       = _env("RECOVERY_INTERVAL", 60, int)

# ============================================================
# AUDIO (HARDWARE) — no tocar salvo que sepas qué haces
# ============================================================
SAMPLERATE              = _env("SAMPLERATE", 44100, int)
SAMPLERATE_GOOGLE       = _env("SAMPLERATE_GOOGLE", 16000, int)
MIC_WARMUP_SECONDS      = _env("MIC_WARMUP_SECONDS", 0.6, float)

# ============================================================
# ESCUCHA
# ============================================================
MIC_UMBRAL              = _env("MIC_UMBRAL", 0.008, float)
ESCUCHA_SILENCIO_CORTE  = _env("ESCUCHA_SILENCIO_CORTE", 0.8, float)
ESCUCHA_ESPERA_MAXIMA   = _env("ESCUCHA_ESPERA_MAXIMA", 8.0, float)
ESCUCHA_DURACION_MAXIMA = _env("ESCUCHA_DURACION_MAXIMA", 6.0, float)
ESCUCHA_CHUNK           = _env("ESCUCHA_CHUNK", 0.3, float)

# ============================================================
# WHISPER (STT local)
# ============================================================
WHISPER_MODELO          = _env("WHISPER_MODELO", "small")
WHISPER_DEVICE          = _env("WHISPER_DEVICE", "cuda")
WHISPER_COMPUTE_TYPE    = _env("WHISPER_COMPUTE_TYPE", "int8_float16")
WHISPER_IDIOMA          = _env("WHISPER_IDIOMA", "es")
WHISPER_BEAM_SIZE       = _env("WHISPER_BEAM_SIZE", 1, int)

# ============================================================
# WAKE WORD
# ============================================================
WAKE_UMBRAL             = _env("WAKE_UMBRAL", 0.005, float)
WAKE_DURACION_MONITOR   = _env("WAKE_DURACION_MONITOR", 1.0, float)
WAKE_DURACION_GRABACION = _env("WAKE_DURACION_GRABACION", 4.0, float)
WAKE_MAX_PALABRAS       = _env("WAKE_MAX_PALABRAS", 4, int)
WAKE_MAX_DISTANCIA      = _env("WAKE_MAX_DISTANCIA", 1, int)

# ============================================================
# TTS / HABLAR
# ============================================================
VOZ                     = _env("VOZ", "es-MX-DaliaNeural")
TTS_MIN_FRAGMENTO       = _env("TTS_MIN_FRAGMENTO", 15, int)
TTS_BUFFER_ORACIONES    = _env("TTS_BUFFER_ORACIONES", 2, int)

# ============================================================
# RUTINAS
# ============================================================
CIUDAD_CLIMA            = _env("CIUDAD_CLIMA", "Cajamarca")

# ============================================================
# MODELOS OLLAMA
# ============================================================
MODELO_PCN = _env("MODELO_PCN", "eli-fast", str)
MODELO_PCV = _env("MODELO_PCV", "qwen2.5:3b", str)
