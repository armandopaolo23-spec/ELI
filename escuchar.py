# ============================================================
# escuchar.py — Escucha optimizada para Eli
#
# OPTIMIZACIÓN 1: Downsample 44100Hz → 16000Hz. Whisper requiere
#   16kHz; resamplear acá ahorra trabajo dentro del modelo.
#
# OPTIMIZACIÓN 2: Recortar el silencio final. Sabemos que hay
#   ~1.5 seg de silencio al final (así detectamos el fin de habla).
#   Lo recortamos antes de transcribir.
#
# OPTIMIZACIÓN 3: STT 100% local con faster-whisper en GPU.
#   Antes: SpeechRecognition+Google → 2-5s + requería internet.
#   Ahora: Whisper small en CUDA → 200-400ms, offline, consistente.
# ============================================================

from __future__ import annotations

import queue
import time
from typing import Any

import numpy as np
import scipy.signal
import sounddevice as sd

import config as cfg
import whisper_stt
from logger import get_logger

log = get_logger(__name__)

# Aliases locales para legibilidad. Todos los valores vienen de config
# y pueden sobreescribirse con ELI_* env vars.
SAMPLERATE = cfg.SAMPLERATE
SAMPLERATE_WHISPER = cfg.SAMPLERATE_GOOGLE   # 16000 Hz; el nombre se mantiene por compat.
WARMUP_SECONDS = cfg.MIC_WARMUP_SECONDS
UMBRAL = cfg.MIC_UMBRAL
SILENCIO_PARA_CORTAR = cfg.ESCUCHA_SILENCIO_CORTE
ESPERA_MAXIMA = cfg.ESCUCHA_ESPERA_MAXIMA
DURACION_MAXIMA = cfg.ESCUCHA_DURACION_MAXIMA
CHUNK = cfg.ESCUCHA_CHUNK

# --- Estado del stream ---

_stream = None
_q: queue.Queue = queue.Queue()


def _callback(indata: Any, frames: int, time_info: Any, status: Any) -> None:
    _q.put(indata.copy())


def calibrar_una_vez() -> None:
    """Inicia el InputStream persistente del micrófono."""
    global _stream
    if _stream is not None:
        return
    log.info("🔧 Iniciando micrófono...")
    _stream = sd.InputStream(
        samplerate=SAMPLERATE,
        channels=1,
        dtype='float32',
        latency='low',
        blocksize=0,
        callback=_callback
    )
    _stream.start()
    time.sleep(WARMUP_SECONDS)
    while not _q.empty():
        _q.get()
    log.info("✅ Micrófono listo.")


def _leer_chunk() -> Any:
    """Lee un bloque de audio del stream. Retorna np.ndarray 1-D."""
    frames = []
    needed = int(SAMPLERATE * CHUNK)
    collected = 0
    while collected < needed:
        chunk = _q.get()
        frames.append(chunk)
        collected += len(chunk)
    return np.concatenate(frames)[:needed].flatten()


def escuchar() -> str:
    """
    Escucha al usuario con detección inteligente de voz y transcribe
    con Whisper local.

    Retorna:
        str: Texto reconocido en minúsculas, o "" si no entendió.
    """
    global _stream
    if _stream is None:
        calibrar_una_vez()

    # Limpiar audio residual del buffer.
    while not _q.empty():
        _q.get()

    log.debug("🎤 Te escucho...")

    # --- Fase 1: Detección de voz (VAD por umbral de volumen) ---
    bloques_audio = []
    hablando = False
    bloques_silencio = 0
    bloques_espera = 0
    bloques_grabados = 0

    bloques_espera_max = int(ESPERA_MAXIMA / CHUNK)
    bloques_silencio_corte = int(SILENCIO_PARA_CORTAR / CHUNK)
    bloques_duracion_max = int(DURACION_MAXIMA / CHUNK)
    BLOQUES_MINIMOS = 3

    while True:
        bloque = _leer_chunk()
        volumen = np.abs(bloque).mean()
        hay_voz = volumen > UMBRAL

        if not hablando:
            if hay_voz:
                hablando = True
                bloques_silencio = 0
                bloques_audio.append(bloque)
                bloques_grabados = 1
            else:
                bloques_espera += 1
                if bloques_espera >= bloques_espera_max:
                    return ""
        else:
            bloques_audio.append(bloque)
            bloques_grabados += 1
            if hay_voz:
                bloques_silencio = 0
            else:
                bloques_silencio += 1
                if bloques_grabados >= BLOQUES_MINIMOS and bloques_silencio >= bloques_silencio_corte:
                    break
            if bloques_grabados >= bloques_duracion_max:
                break

    if not bloques_audio:
        return ""

    audio = np.concatenate(bloques_audio).flatten()

    # --- OPTIMIZACIÓN 2: Recortar silencio final ---
    # Sabemos que los últimos bloques_silencio bloques son silencio.
    # Dejamos 0.2 seg de cola para que Whisper detecte fin de frase.
    muestras_silencio = int(bloques_silencio * CHUNK * SAMPLERATE)
    muestras_cola = int(0.2 * SAMPLERATE)

    if muestras_silencio > muestras_cola:
        recorte = muestras_silencio - muestras_cola
        if recorte < len(audio):
            audio = audio[:-recorte]

    # --- OPTIMIZACIÓN 1: Downsample 44100 → 16000 ---
    # Whisper requiere 16kHz. resample_poly(audio, 160, 441) hace el
    # ratio exacto 16000/44100 con un filtro polifase eficiente.
    audio_16k = scipy.signal.resample_poly(audio, 160, 441).astype(np.float32)

    # --- OPTIMIZACIÓN 3: Transcribir con Whisper local ---
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
    whisper_stt.precarga()
    calibrar_una_vez()

    print("=== Prueba de escucha local con Whisper ===\n")

    inicio = time.time()
    resultado = escuchar()
    elapsed = time.time() - inicio

    if resultado:
        print(f'\n✅ Escuché: "{resultado}" ({elapsed:.2f}s total)')
    else:
        print(f"\n❌ No se detectó frase ({elapsed:.2f}s)")
