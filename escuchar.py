# ============================================================
# escuchar.py — Escucha optimizada para Eli
#
# OPTIMIZACIÓN 1: Downsample 44100Hz → 16000Hz antes de enviar
#   a Google. El audio de voz solo necesita 16kHz. Esto reduce
#   el tamaño del archivo WAV ~2.75x, haciendo el upload a
#   Google ~2.75x más rápido.
#
# OPTIMIZACIÓN 2: Recortar el silencio final. Sabemos que hay
#   ~1.5 seg de silencio al final (así detectamos el fin de habla).
#   Enviamos ese silencio a Google por nada. Lo recortamos.
#
# OPTIMIZACIÓN 3: BytesIO en vez de archivo temporal. Igual que
#   hablar.py, evitamos el disco.
#
# Ganancia total: ~300-600ms menos en el reconocimiento.
# ============================================================

from __future__ import annotations

from typing import Any

import sounddevice as sd
import numpy as np
import scipy.io.wavfile as wav
import scipy.signal       # Para resampleo (downsample).
import speech_recognition as sr
import io                  # BytesIO para evitar disco.
import os
import queue
import time

import config as cfg
from logger import get_logger

log = get_logger(__name__)

# Aliases locales para legibilidad. Todos los valores vienen de config
# y pueden sobreescribirse con ELI_* env vars.
SAMPLERATE = cfg.SAMPLERATE
SAMPLERATE_GOOGLE = cfg.SAMPLERATE_GOOGLE
WARMUP_SECONDS = cfg.MIC_WARMUP_SECONDS
UMBRAL = cfg.MIC_UMBRAL
SILENCIO_PARA_CORTAR = cfg.ESCUCHA_SILENCIO_CORTE
ESPERA_MAXIMA = cfg.ESCUCHA_ESPERA_MAXIMA
DURACION_MAXIMA = cfg.ESCUCHA_DURACION_MAXIMA
CHUNK = cfg.ESCUCHA_CHUNK

# --- Estado del stream ---

_stream = None
_q = queue.Queue()


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
    Escucha al usuario con detección inteligente de voz.
    Optimizada: downsample + trim + BytesIO.

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

    # --- Fase 1: Detección de voz (igual que antes) ---
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
    # Recortamos todo menos 0.2 seg de cola (un poco de silencio
    # ayuda a Google a detectar el fin de la frase).
    muestras_silencio = int(bloques_silencio * CHUNK * SAMPLERATE)
    muestras_cola = int(0.2 * SAMPLERATE)  # Dejar 0.2 seg.

    if muestras_silencio > muestras_cola:
        recorte = muestras_silencio - muestras_cola
        if recorte < len(audio):
            audio = audio[:-recorte]

    # --- OPTIMIZACIÓN 1: Downsample 44100 → 16000 ---
    # scipy.signal.resample_poly hace un resampleo eficiente.
    # Reduce de 44100 a 16000 muestras por segundo.
    # Esto hace el audio ~2.75x más pequeño.
    #
    # La razón 16000/44100 se simplifica a 160/441.
    # resample_poly(audio, up, down) primero interpola "up" veces
    # y luego decima "down" veces.
    audio_16k = scipy.signal.resample_poly(audio, 160, 441)

    # Convertir a int16 para el WAV.
    audio_int16 = (np.clip(audio_16k, -1.0, 1.0) * 32767).astype(np.int16)

    # --- OPTIMIZACIÓN 3: BytesIO en vez de disco ---
    buffer = io.BytesIO()
    wav.write(buffer, SAMPLERATE_GOOGLE, audio_int16)
    buffer.seek(0)

    # --- Reconocimiento con Google Speech ---
    reconocedor = sr.Recognizer()
    with sr.AudioFile(buffer) as fuente:
        audio_sr = reconocedor.record(fuente)

    try:
        texto = reconocedor.recognize_google(audio_sr, language="es-ES")
        return texto.lower()
    except sr.UnknownValueError:
        return ""
    except sr.RequestError:
        log.warning("Sin conexión a internet (Google Speech).")
        return ""


# --- Prueba directa ---
if __name__ == "__main__":
    calibrar_una_vez()

    print("=== Prueba de escucha optimizada ===\n")

    inicio = time.time()
    resultado = escuchar()
    elapsed = time.time() - inicio

    if resultado:
        print(f'\n✅ Escuché: "{resultado}" ({elapsed:.2f}s total)')
    else:
        print(f"\n❌ No se detectó frase ({elapsed:.2f}s)")
