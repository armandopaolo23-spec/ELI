import sounddevice as sd
import numpy as np
import scipy.signal
import whisper_stt
import time

SAMPLERATE = 44100
SAMPLERATE_GOOGLE = 16000

print("=== DIAGNÓSTICO DE AUDIO ===")
print("Habla CLARO y FUERTE durante 3 segundos...")
print("Grabando en 3...")
time.sleep(1)
print("2...")
time.sleep(1)
print("1...")
time.sleep(1)
print("🎤 ¡HABLA AHORA! (3 segundos)")

# Grabar 3 segundos
audio = sd.rec(int(3 * SAMPLERATE), samplerate=SAMPLERATE, channels=1, dtype='float32')
sd.wait()

audio_mono = audio[:, 0]

# Análisis del audio
volumen_max = np.abs(audio_mono).max()
volumen_medio = np.abs(audio_mono).mean()
volumen_rms = np.sqrt(np.mean(audio_mono**2))

print(f"\n📊 ANÁLISIS:")
print(f"  Volumen máximo: {volumen_max:.4f}")
print(f"  Volumen medio:  {volumen_medio:.6f}")
print(f"  Volumen RMS:    {volumen_rms:.6f}")
print(f"  UMBRAL actual:  0.008")

if volumen_medio < 0.001:
    print("  ⚠️ AUDIO MUY BAJO - habla más fuerte o acerca el micrófono")
elif volumen_medio > 0.05:
    print("  ⚠️ AUDIO MUY ALTO - aléjate del micrófono")
else:
    print("  ✅ Volumen parece OK")

# Downsample a 16kHz
audio_16k = scipy.signal.resample(audio_mono, int(len(audio_mono) * SAMPLERATE_GOOGLE / SAMPLERATE))

# Transcribir
print("\n🔄 Transcribiendo con Whisper...")
whisper_stt.precarga()
texto = whisper_stt.transcribir(audio_16k.astype(np.float32))

print(f"\n📝 TRANSCRIPCIÓN:")
print(f"  '{texto}'")
print("\n¿Es correcto? (compara con lo que dijiste)")
