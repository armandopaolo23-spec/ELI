# ============================================================
# escuchar.py — Escucha optimizada para Eli
#
# ARQUITECTURA (post-VAD):
#   1. vad_detector.detectar_audio() captura audio a 16kHz y usa
#      Silero VAD para detectar fin de habla en tiempo real
#      (~150-250ms de latencia contra los 1.5s del timeout fijo).
#   2. whisper_stt.transcribir() pasa el audio a Whisper local.
#
# Este módulo es ahora un orquestador delgado. La lógica de captura
# vive en vad_detector.py; la transcripción en whisper_stt.py.
# ============================================================

from __future__ import annotations

import time

import vad_detector
import whisper_stt
from logger import get_logger

log = get_logger(__name__)

# Re-export del queue interno de vad_detector para que main.py pueda
# drenar audio residual tras detectar la wake word sin tener que
# importar vad_detector directamente.
_q = vad_detector._q


def calibrar_una_vez() -> None:
    """Inicia el stream del micrófono (delegado a vad_detector)."""
    vad_detector.calibrar_stream()


def escuchar() -> str:
    """Escucha al usuario y transcribe con Whisper.

    El fin de habla lo detecta Silero VAD en tiempo real; ya no hay
    timeout fijo de silencio. El audio retorna a 16kHz float32 listo
    para Whisper, sin necesidad de downsampling ni WAV intermedio.

    Retorna:
        str: Texto reconocido en minúsculas, o "" si no hubo voz.
    """
    log.debug("🎤 Te escucho...")

    audio_16k = vad_detector.detectar_audio()
    if audio_16k is None or len(audio_16k) == 0:
        return ""

    t0 = time.time()
    try:
        texto = whisper_stt.transcribir(audio_16k)
    except Exception as error:
        log.warning("Whisper falló: %s", error)
        return ""
    t_stt = time.time() - t0
    log.debug("⏱️ stt: %.2fs", t_stt)

    return texto


# --- Prueba directa ---
if __name__ == "__main__":
    vad_detector.precarga()
    whisper_stt.precarga()
    calibrar_una_vez()

    print("=== Prueba de escucha con Silero VAD + Whisper ===\n")

    inicio = time.time()
    resultado = escuchar()
    elapsed = time.time() - inicio

    if resultado:
        print(f'\n✅ Escuché: "{resultado}" ({elapsed:.2f}s total)')
    else:
        print(f"\n❌ No se detectó frase ({elapsed:.2f}s)")
