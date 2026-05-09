# ============================================================
# wake_word.py — Detección de wake word para Eli (anti falsos positivos)
#
# Problema anterior: "elite", "delin", "celis", "jajaja" activaban
# a Eli porque usábamos "if wake in texto" — una búsqueda de
# subcadena que acepta cualquier palabra que CONTENGA "eli".
#
# Solución nueva: 3 filtros en cascada:
#
# Filtro 1 — LARGO: Si Google transcribió más de 4 palabras,
#   descartamos. Un wake word es corto ("Eli", "Hey Eli"),
#   no una frase completa.
#
# Filtro 2 — EXACTO: Comparamos cada palabra individual del
#   texto contra una lista de formas exactas. "eli" coincide,
#   "elite" no (porque "elite" != "eli").
#
# Filtro 3 — SIMILITUD: Si no hay coincidencia exacta, usamos
#   distancia de Levenshtein para encontrar palabras MUY
#   similares. "elí" tiene distancia 0 de "eli" (normalizado),
#   "delin" tiene distancia 2 → se rechaza.
# ============================================================

import sounddevice as sd
import numpy as np
import scipy.io.wavfile as wav
import speech_recognition as sr
import tempfile
import os
import queue
import time

# --- Configuración del micrófono ---

SAMPLERATE = 44100
WARMUP_SECONDS = 0.6     # Tiempo de calentamiento del micrófono.
DURACION_MONITOR = 1.0   # Segundos por bloque de monitoreo de volumen.
DURACION_WAKE = 4.0      # Segundos de grabación para verificar wake word.
UMBRAL = 0.005            # Volumen mínimo para considerar que hay voz.

# --- Configuración del wake word ---

# Formas EXACTAS que aceptamos. Cada entrada es una frase completa
# que debe coincidir con UNA palabra o grupo de palabras del texto.
# Ya NO incluimos "elite", "belly", "elli" — esos eran la causa
# de los falsos positivos.
WAKE_EXACTOS = {
    "eli", "elí", "ely", "elí",
}

# Frases de dos palabras. Las verificamos como par.
WAKE_FRASES = {
    "hey eli", "hey elí", "oye eli", "oye elí",
    "ey eli", "ey elí", "hey ely", "oye ely",
}

# Máximo de palabras que aceptamos en la transcripción.
# "Hey Eli" = 2 palabras → ok.
# "Eli qué hora es" = 4 palabras → ok (puede pasar).
# "Estaba hablando con mi amigo sobre eli" = 8 → rechazado.
# Si alguien dijo una frase larga, no estaba llamando a Eli.
MAX_PALABRAS = 4

# Distancia de Levenshtein máxima para considerar una coincidencia.
# 1 = acepta UN carácter de diferencia.
#   "eli" vs "eli" → distancia 0 → ✅
#   "elí" vs "eli" → distancia 0 (normalizamos tildes) → ✅
#   "elli" vs "eli" → distancia 1 → ✅
#   "heli" vs "eli" → distancia 1 → ✅
#   "elite" vs "eli" → distancia 2 → ❌
#   "delin" vs "eli" → distancia 3 → ❌
#   "celis" vs "eli" → distancia 2 → ❌
MAX_DISTANCIA = 1

# --- Estado del stream ---

_stream = None
_q = queue.Queue()


# ============================================================
# DISTANCIA DE LEVENSHTEIN
# ============================================================

def _levenshtein(s1, s2):
    """
    Calcula la distancia de edición entre dos cadenas.

    La distancia de Levenshtein cuenta el número MÍNIMO de
    operaciones (insertar, eliminar, reemplazar un carácter)
    para transformar s1 en s2.

    Ejemplos:
        "eli" → "eli"   = 0 (iguales)
        "eli" → "elli"  = 1 (insertar una 'l')
        "eli" → "heli"  = 1 (insertar una 'h')
        "eli" → "elite" = 2 (insertar 't' y 'e')
        "eli" → "delin" = 3 (reemplazar 'e'→'d', insertar 'n', etc.)

    Usa programación dinámica: una tabla donde cada celda [i][j]
    guarda la distancia entre los primeros i caracteres de s1
    y los primeros j caracteres de s2.
    """
    # Si alguna cadena está vacía, la distancia es el largo de la otra.
    if len(s1) == 0:
        return len(s2)
    if len(s2) == 0:
        return len(s1)

    # Crear la tabla. Usamos solo dos filas para ahorrar memoria:
    # la fila anterior y la fila actual.
    fila_anterior = list(range(len(s2) + 1))
    fila_actual = [0] * (len(s2) + 1)

    for i in range(1, len(s1) + 1):
        fila_actual[0] = i

        for j in range(1, len(s2) + 1):
            # Costo: 0 si los caracteres son iguales, 1 si son diferentes.
            costo = 0 if s1[i - 1] == s2[j - 1] else 1

            fila_actual[j] = min(
                fila_actual[j - 1] + 1,      # Inserción
                fila_anterior[j] + 1,         # Eliminación
                fila_anterior[j - 1] + costo  # Sustitución
            )

        # La fila actual se convierte en la anterior para la siguiente iteración.
        fila_anterior = fila_actual[:]

    return fila_actual[len(s2)]


def _normalizar(texto):
    """
    Normaliza texto para comparación: quita tildes y pasa a minúsculas.

    Esto hace que "Elí" y "eli" sean idénticos para la comparación.
    Sin normalizar, "elí" tendría distancia 1 de "eli" por la tilde,
    lo cual gastaría nuestro margen de error.
    """
    reemplazos = {
        "á": "a", "é": "e", "í": "i", "ó": "o", "ú": "u",
        "ä": "a", "ë": "e", "ï": "i", "ö": "o", "ü": "u",
    }
    texto = texto.lower()
    for original, reemplazo in reemplazos.items():
        texto = texto.replace(original, reemplazo)
    return texto


# ============================================================
# VERIFICACIÓN DEL WAKE WORD (los 3 filtros)
# ============================================================

def _es_wake_word(texto):
    """
    Verifica si el texto transcrito es el wake word.

    Aplica 3 filtros en cascada. Si alguno aprueba, retorna True.
    Si todos rechazan, retorna False.

    Args:
        texto (str): Transcripción de Google Speech (ya en minúsculas).

    Retorna:
        bool: True si es el wake word, False si no.
    """

    texto = texto.strip()
    if not texto:
        return False

    palabras = texto.split()

    # ─── Filtro 1: LARGO ───
    # Si la frase es muy larga, descartamos inmediatamente.
    # Un wake word es 1-4 palabras máximo.
    if len(palabras) > MAX_PALABRAS:
        print(f"   ❌ Frase muy larga ({len(palabras)} palabras): '{texto}'")
        return False

    # Normalizamos todo para las comparaciones.
    texto_norm = _normalizar(texto)
    palabras_norm = texto_norm.split()

    # ─── Filtro 2: COINCIDENCIA EXACTA ───
    # Verificamos si la frase completa coincide con alguna frase wake.
    # Esto cubre "hey eli", "oye eli", etc.
    if texto_norm in {_normalizar(f) for f in WAKE_FRASES}:
        print(f"   ✅ Frase exacta: '{texto}'")
        return True

    # Verificamos si alguna palabra individual coincide exactamente.
    # Esto cubre "eli" dicho solo o dentro de algo corto como "eli hola".
    exactos_norm = {_normalizar(w) for w in WAKE_EXACTOS}
    for palabra in palabras_norm:
        if palabra in exactos_norm:
            print(f"   ✅ Palabra exacta: '{palabra}' en '{texto}'")
            return True

    # ─── Filtro 3: SIMILITUD (Levenshtein) ───
    # Si no hubo coincidencia exacta, buscamos palabras MUY similares.
    # Google a veces transcribe "Eli" como "heli", "elli", "eli.", etc.
    # Pero NO queremos aceptar "elite" (distancia 2) ni "delin" (distancia 3).
    objetivo = "eli"  # La forma canónica contra la que comparamos.

    for palabra in palabras_norm:
        dist = _levenshtein(palabra, objetivo)
        if dist <= MAX_DISTANCIA:
            print(f"   ✅ Similar: '{palabra}' (distancia {dist} de '{objetivo}')")
            return True

    # También verificamos similitud contra "hey eli" como bloque.
    # Esto cubre "hey elli", "ey eli", etc.
    if len(palabras_norm) >= 2:
        # Tomamos las primeras dos palabras como posible frase wake.
        frase_dos = " ".join(palabras_norm[:2])
        for frase_wake in ["hey eli", "oye eli", "ey eli"]:
            dist = _levenshtein(frase_dos, frase_wake)
            # Para frases de 2 palabras, permitimos distancia 2
            # porque hay más caracteres donde puede haber error.
            if dist <= 2:
                print(f"   ✅ Frase similar: '{frase_dos}' (distancia {dist} de '{frase_wake}')")
                return True

    # Ningún filtro aprobó.
    print(f"   ❌ No coincide: '{texto}'")
    return False


# ============================================================
# STREAM DE AUDIO
# ============================================================

def _callback(indata, frames, time_info, status):
    """Callback del stream: mete cada bloque de audio en la cola."""
    _q.put(indata.copy())


def _iniciar_stream():
    """Inicia el InputStream persistente del micrófono."""
    global _stream
    print("🔧 Iniciando micrófono para wake word...")
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
    print("✅ Micrófono listo.")


def _leer_audio(segundos):
    # Limpiar TODO el audio acumulado antes de grabar
    while not _q.empty():
        _q.get()
    frames_needed = int(SAMPLERATE * segundos)
    frames = []
    collected = 0
    while collected < frames_needed:
        chunk = _q.get()
        frames.append(chunk)
        collected += len(chunk)
    return np.concatenate(frames)[:frames_needed].flatten()


def _reconocer(audio):
    """Envía audio a Google Speech y retorna el texto."""
    archivo = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
    nombre = archivo.name
    archivo.close()
    try:
        audio_int16 = (np.clip(audio, -1.0, 1.0) * 32767).astype(np.int16)
        wav.write(nombre, SAMPLERATE, audio_int16)
        reconocedor = sr.Recognizer()
        with sr.AudioFile(nombre) as fuente:
            audio_sr = reconocedor.record(fuente)
        texto = reconocedor.recognize_google(audio_sr, language="es-ES")
        return texto.lower()
    except Exception:
        return ""
    finally:
        try:
            os.unlink(nombre)
        except OSError:
            pass


# ============================================================
# FUNCIÓN PRINCIPAL
# ============================================================

def esperar_wake_word():
    """
    Bloquea hasta que el usuario diga "Eli" o "Hey Eli".
    Usa los 3 filtros para minimizar falsos positivos.

    Retorna:
        True cuando detecta el wake word.
        False si hay un error crítico o Ctrl+C.
    """
    global _stream

    if _stream is None:
        _iniciar_stream()

    print("💤 Esperando wake word... (di 'Eli' o 'Hey Eli')")

    while True:
        try:
            # Limpiar cola de audio acumulado
            audio = _leer_audio(DURACION_MONITOR)
            volumen = np.abs(audio).mean()
    

            if volumen <= UMBRAL:
                continue

            print("   👂 Detecté voz, verificando...")
            audio_wake = _leer_audio(DURACION_WAKE)
            texto = _reconocer(audio_wake)

            if not texto:
                print("   No entendí. Sigo esperando...")
                continue

            # Aquí está el cambio: en vez de "if any(wake in texto)",
            # usamos nuestro sistema de 3 filtros.
            if _es_wake_word(texto):
                return True
            else:
                print("   Sigo esperando...")

        except KeyboardInterrupt:
            return False


# --- Prueba directa ---
if __name__ == "__main__":
    # ─── Test de los filtros sin micrófono ───
    print("=== Test de filtros (sin micrófono) ===\n")

    pruebas = [
        # Debe aceptar
        ("eli", True),
        ("Elí", True),
        ("hey eli", True),
        ("oye eli", True),
        ("ey eli", True),
        ("heli", True),          # distancia 1 de "eli"
        ("elli", True),          # distancia 1 de "eli"
        ("eli hola", True),      # corto + contiene "eli"
        ("hey elli", True),      # frase similar

        # Debe rechazar
        ("elite", False),        # distancia 2
        ("delin", False),        # distancia 3
        ("celis", False),        # distancia 2
        ("jajaja", False),       # nada que ver
        ("belly", False),        # distancia 2
        ("estaba hablando con mi amigo sobre eli", False),  # frase larga
        ("la película de ayer estuvo genial", False),        # nada que ver
    ]

    aciertos = 0
    for texto, esperado in pruebas:
        resultado = _es_wake_word(texto)
        estado = "✅" if resultado == esperado else "❌ FALLO"
        aciertos += 1 if resultado == esperado else 0
        print(f"  {estado}  '{texto}' → {resultado} (esperado: {esperado})\n")

    print(f"\nResultado: {aciertos}/{len(pruebas)} correctos\n")

    # ─── Test con micrófono ───
    print("=== Test con micrófono ===")
    print("Di 'Eli' o 'Hey Eli' para activar.\n")
    resultado = esperar_wake_word()
    if resultado:
        print("\n✅ ¡Wake word detectado!")
    else:
        print("\n❌ Interrumpido.")
