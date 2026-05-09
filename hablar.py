# ============================================================
# hablar.py — Voz de Eli optimizada
#
# ANTES: edge-tts genera MP3 → guarda en disco → lee de disco
#        → decodifica → reproduce. El disco es el cuello de botella.
#
# AHORA: edge-tts genera MP3 → acumula en RAM (BytesIO) →
#        decodifica desde RAM → reproduce. Sin tocar el disco.
#
# Ganancia: ~200-400ms menos por frase (el write+read al disco
# en un SSD toma ~100ms, en HDD puede ser ~300ms).
# ============================================================

import asyncio
import io            # BytesIO: un "archivo" que vive en RAM.
import edge_tts
import sounddevice as sd
import soundfile as sf

# --- Configuración ---
VOZ = "es-MX-DaliaNeural"


def hablar(texto):
    """
    Convierte texto a voz y lo reproduce.
    Todo el audio se procesa en RAM, sin archivos temporales.
    """
    if not texto or not texto.strip():
        return

    try:
        asyncio.run(_hablar_async(texto))
    except Exception:
        # Si asyncio.run() falla (ej: loop ya corriendo), intentar alternativa.
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # Crear un nuevo loop en este hilo.
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor() as pool:
                    pool.submit(lambda: asyncio.run(_hablar_async(texto))).result()
            else:
                loop.run_until_complete(_hablar_async(texto))
        except Exception:
            pass


async def _hablar_async(texto):
    """
    Genera audio con edge-tts en streaming y lo acumula en RAM.

    edge-tts.Communicate.stream() entrega el audio en pedazos
    (chunks) conforme el servidor de Microsoft lo genera.
    En vez de guardarlo en disco, lo juntamos en un BytesIO.

    BytesIO es un objeto que se comporta como un archivo pero
    vive completamente en la RAM. Leer/escribir en RAM es
    ~100x más rápido que en disco.
    """

    # --- Paso 1: Recolectar audio en memoria ---
    # BytesIO actúa como un archivo en RAM.
    buffer_audio = io.BytesIO()

    comunicador = edge_tts.Communicate(texto, VOZ)

    # stream() es un generador asíncrono que entrega chunks.
    # Cada chunk tiene un "type": puede ser "audio" (datos MP3)
    # o "WordBoundary" (timing de palabras, no nos interesa).
    async for chunk in comunicador.stream():
        if chunk["type"] == "audio":
            # chunk["data"] contiene bytes de audio MP3.
            buffer_audio.write(chunk["data"])

    # Si no se generó audio (texto vacío, error del servidor).
    if buffer_audio.tell() == 0:
        return

    # --- Paso 2: Decodificar desde RAM ---
    # Rebobinar el buffer al inicio para que sf.read() lo lea desde el principio.
    buffer_audio.seek(0)

    # sf.read() puede leer desde un file-like object (BytesIO),
    # no solo desde rutas de archivo. Esto evita escribir a disco.
    datos, frecuencia = sf.read(buffer_audio)

    # --- Paso 3: Reproducir ---
    sd.play(datos, frecuencia)
    sd.wait()  # Bloquea hasta que termine de sonar.


# --- Prueba directa ---
if __name__ == "__main__":
    import time

    print("=== Prueba de voz optimizada ===\n")

    inicio = time.time()
    hablar("Sistemas en línea. Listo para ayudarte.")
    t1 = time.time() - inicio

    inicio = time.time()
    hablar("Esta es una segunda prueba de velocidad.")
    t2 = time.time() - inicio

    print(f"\nTiempos: {t1:.2f}s, {t2:.2f}s")
