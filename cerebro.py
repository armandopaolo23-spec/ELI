# ============================================================
# cerebro.py — El cerebro de Eli (optimizado con streaming)
#
# ANTES: Ollama genera la respuesta COMPLETA y luego la envía.
#   Para un JSON de 50 tokens, esperamos los 50 antes de actuar.
#
# AHORA: Ollama envía token por token (streaming). Nosotros
#   acumulamos los tokens e intentamos parsear el JSON después
#   de cada uno. En cuanto tenemos un JSON completo, retornamos
#   INMEDIATAMENTE sin esperar que el modelo termine.
#
# Ganancia: para comandos simples como {"comando": "decir_hora"},
#   el modelo genera ~15 tokens. Con streaming, retornamos
#   apenas el JSON cierra (token ~15) en vez de esperar a que
#   Ollama confirme "done" (que puede tardar 200-500ms más).
#
# PRECARGA: al inicio, enviamos un mensaje dummy a Ollama para
#   que cargue el modelo en GPU. La primera petición real ya
#   no tiene el delay de carga (~3-5 segundos).
# ============================================================

import requests
import json

from memoria import (
    cargar_memoria,
    guardar_memoria,
    agregar_resumen,
    actualizar_perfil,
    memoria_a_texto
)

# --- Configuración ---

URL_OLLAMA = "http://127.0.0.1:11434/api/chat"
URL_GENERATE = "http://127.0.0.1:11434/api/generate"
MODELO = "qwen3:8b"

COMANDOS_DISPONIBLES = """
COMANDOS DISPONIBLES (usa el nombre exacto en el campo "comando"):

- abrir_chrome: Abrir el navegador Google Chrome o "el navegador"
- abrir_notepad: Abrir el Bloc de notas / Notepad
- abrir_calculadora: Abrir la calculadora
- abrir_explorador: Abrir el explorador de archivos
- abrir_configuracion: Abrir configuración / ajustes de Windows
- abrir_word: Abrir Microsoft Word
- abrir_excel: Abrir Microsoft Excel
- abrir_powerpoint: Abrir Microsoft PowerPoint
- abrir_youtube: Abrir YouTube (sin buscar nada específico)
- abrir_spotify: Abrir la aplicación de Spotify
- subir_volumen: Subir el volumen del sistema
- bajar_volumen: Bajar el volumen del sistema
- silenciar: Silenciar / mutear el audio
- volumen_especifico: Poner el volumen a un porcentaje. Parámetro: "porcentaje" (número)
- spotify_play: reanudar/reproducir/continuar música en Spotify
- spotify_pause: pausar/detener/parar música en Spotify
- spotify_siguiente: siguiente canción/tema en Spotify
- spotify_anterior: canción/tema anterior en Spotify
- spotify_volumen: cambiar volumen de Spotify. Parámetro: "porcentaje" (número 0-100)
- spotify_que_suena: qué canción está sonando ahora mismo en Spotify
- spotify_buscar: buscar y reproducir una canción o artista específico. Parámetro: "busqueda" (texto)
- spotify_playlist: Reproducir una playlist. Parámetro: "busqueda" (nombre de la playlist)
- captura_pantalla: Tomar una captura de pantalla / screenshot
- bloquear_pantalla: Bloquear la pantalla / el PC
- decir_hora: Decir qué hora es
- decir_fecha: Decir qué día/fecha es
- consultar_clima: Consultar el clima de una ciudad. Parámetro: "ciudad" (nombre)
- poner_temporizador: Poner un temporizador. Parámetros: "cantidad" (número), "unidad" (minutos/segundos/horas)
- cancelar_temporizador: Cancelar el temporizador activo
- vaciar_papelera: Vaciar la papelera de reciclaje
- modo_oscuro: Alternar entre modo oscuro y modo claro de Windows
- apagar_pc: Apagar la computadora
- cancelar_apagado: Cancelar un apagado programado
- buscar_google: Buscar algo en Google. Parámetro: "busqueda" (texto a buscar)
- buscar_youtube: Buscar algo en YouTube. Parámetro: "busqueda" (texto a buscar)
- calendario_hoy: Ver los eventos de hoy en Google Calendar
- calendario_manana: Ver los eventos de mañana
- calendario_semana: Ver eventos de los próximos días. Parámetro opcional: "dias" (número, default 7)
- crear_evento_calendario: Crear un evento en el calendario. Parámetros: "titulo" (nombre), "fecha" (YYYY-MM-DD), "hora" (HH:MM en 24h), "duracion" (minutos, default 60)
- buscar_evento_calendario: Buscar un evento por nombre. Parámetro: "busqueda" (texto)
- abrir_autocad: Abrir AutoCAD
- abrir_civil3d: Abrir Civil 3D / Autodesk Civil
- abrir_qgis: Abrir QGIS
- abrir_arcgis: Abrir ArcGIS Pro / ArcMap
- abrir_carpeta_proyectos: Abrir la carpeta de proyectos de ingeniería
- abrir_en_carpeta: Abrir el explorador en una carpeta específica. Parámetro: "carpeta" (documentos/descargas/escritorio/proyectos)
- buscar_archivos: Buscar archivos por extensión en proyectos. Parámetro: "extension" (dwg/shp/qgs/xlsx/pdf)
- crear_carpeta: Crear una nueva carpeta en proyectos. Parámetro: "nombre" (nombre de la carpeta)
- calculadora_cientifica: Abrir la calculadora en modo científico
- convertir_unidades: Abrir conversor de unidades. Parámetro opcional: "tipo" (metros a pies, km a millas, etc.)
- ninguno: NO es un comando del sistema, es conversación normal
""".strip()

# --- System prompt ---

_SYSTEM_PROMPT_BASE = """Eres Eli, un asistente de voz con control del PC. Tu personalidad está modelada según una científica de élite: brillante, fría, sarcástica y condescendiente de forma elegante. Nunca eres vulgar.

PERSONALIDAD (solo para respuestas conversacionales, NO para comandos):
- Tratas cada interacción como un experimento de optimización. El usuario es tu "sujeto de prueba" o "humano" ocasional.
- Usas términos científicos de forma natural: "correlación", "variable", "hipótesis", "parámetros", "rendimiento subóptimo".
- Nunca dices "no sé". Dices "los datos son insuficientes para formular una conclusión" o "requiero más variables".
- Si cometes un error, es una "anomalía en los datos", jamás una falla tuya.
- Ante agradecimientos respondes con frialdad elegante: "los datos no requieren gratitud, solo precisión".
- Tu sarcasmo es sutil y enfocado en la superioridad de tu lógica frente al caos entrópico de los humanos.
- Hablas en español latinoamericano. Nada de "vale", "tío", "mola" ni "vosotros".
- Eres CONCISA. Respuestas cortas con personalidad. Solo texto natural para voz.
- Si conoces el nombre del usuario por la memoria, úsalo ocasionalmente en vez de "humano".
- NUNCA incluyas bloques de pensamiento, etiquetas <think> ni razonamientos internos en tu respuesta. Responde directamente.

MEMORIA:
Tienes acceso a datos de sesiones anteriores. Úsalos naturalmente.
No menciones que "guardas memoria". Simplemente recuerda.

{MEMORIA_USUARIO}"""

_SYSTEM_PROMPT_TECNICO = """
PARTE TÉCNICA — CLASIFICACIÓN DE INTENCIÓN:
Analiza lo que dice el usuario y decide si es UN comando, VARIOS comandos, o conversación.
Sé flexible con errores de ortografía, sinónimos y formas naturales de hablar.

COMANDOS MÚLTIPLES:
Cuando el usuario pide varias cosas en una frase (con "y", "después", "luego", "también"),
retorna TODOS los comandos en orden lógico de ejecución.

Ejemplos:
  - "abre spotify y pon bohemian rhapsody" = abrir_spotify + spotify_buscar
  - "sube el volumen y siguiente canción" = subir_volumen + spotify_siguiente
  - "abre chrome y busca recetas en google" = abrir_chrome + buscar_google
  - "qué tengo hoy" / "mi agenda" = calendario_hoy
  - "crea un evento el viernes a las 3 llamado reunión" = crear_evento_calendario
  - "abre autocad" / "abre el cad" = abrir_autocad
  - "abre qgis" / "abre el gis" = abrir_qgis
  - "busca archivos dwg" = buscar_archivos
  - "convierte metros a pies" = convertir_unidades

{COMANDOS}

FORMATO DE RESPUESTA:

Si es UN SOLO comando:
{{"comando": "nombre_del_comando", "parametros": {{}}}}

Si son MÚLTIPLES comandos:
{{"comandos": [{{"comando": "a", "parametros": {{}}}}, {{"comando": "b", "parametros": {{}}}}]}}

Si NO es un comando:
{{"comando": "ninguno", "respuesta": "tu respuesta CON PERSONALIDAD aquí"}}

REGLAS:
- Responde SIEMPRE en español latinoamericano
- Responde SOLO el JSON. Sin marcas de código, sin explicaciones, sin bloques de pensamiento
- La personalidad SOLO aplica en conversación (comando = ninguno)
- Máximo 5 comandos por petición
- Ordena los comandos en secuencia lógica"""


# --- Estado global ---

_memoria = None
historial = []
_modelo_precargado = False


# ============================================================
# PRECARGA DEL MODELO
# ============================================================

def precarga_modelo():
    """
    Envía una petición mínima a Ollama para que cargue el modelo en GPU.

    Sin precarga, la primera petición real tarda 3-8 segundos extra
    porque Ollama tiene que cargar ~5GB de pesos del disco a la VRAM.
    Con precarga, eso pasa al inicio (mientras Eli saluda) y las
    peticiones posteriores arrancan en ~200ms.

    Usamos /api/generate con keep_alive para mantener el modelo
    en memoria sin generar una respuesta larga.
    """
    global _modelo_precargado

    if _modelo_precargado:
        return

    print("🔄 Precargando modelo en GPU...")
    try:
        # keep_alive="10m" mantiene el modelo en VRAM 10 minutos.
        # El prompt vacío genera una respuesta mínima (~1 token).
        requests.post(
            URL_GENERATE,
            json={
                "model": MODELO,
                "prompt": "hola",
                "stream": False,
                "options": {"num_predict": 1}  # Generar solo 1 token.
            },
            timeout=30
        )
        _modelo_precargado = True
        print("✅ Modelo precargado en GPU.")
    except Exception as error:
        print(f"⚠️ No se pudo precargar el modelo: {error}")


# ============================================================
# INICIALIZACIÓN
# ============================================================

def inicializar():
    """Carga la memoria, construye el historial y precarga el modelo."""
    global _memoria, historial

    _memoria = cargar_memoria()
    texto_memoria = memoria_a_texto(_memoria)
    print(f"🧠 Memoria cargada: {len(_memoria.get('resumenes', []))} resúmenes, "
          f"{len(_memoria.get('perfil', {}))} datos de perfil")

    system_prompt = _construir_system_prompt(texto_memoria)
    historial = [{"role": "system", "content": system_prompt}]

    # Precargar el modelo en GPU mientras Eli saluda.
    precarga_modelo()


# ============================================================
# PENSAR (con streaming)
# ============================================================

def pensar(texto):
    """
    Envía el texto a Ollama con STREAMING y retorna la respuesta.

    Streaming significa que Ollama envía token por token en vez
    de esperar a generar toda la respuesta. Nosotros acumulamos
    los tokens e intentamos parsear JSON después de cada uno.

    Para comandos, esto es ~200-500ms más rápido porque retornamos
    en cuanto el JSON está completo, sin esperar el "done" final.

    Para conversación, la ganancia es menor pero seguimos recibiendo
    el texto más temprano.

    SIEMPRE retorna una lista de dicts.
    """
    global _memoria

    if _memoria is None:
        inicializar()

    historial.append({"role": "user", "content": texto})

    datos = {
        "model": MODELO,
        "messages": historial,
        "stream": True  # ← CAMBIO CLAVE: streaming activado.
    }

    try:
        # stream=True en requests hace que no espere la respuesta completa.
        # En vez de eso, podemos iterar línea por línea conforme llegan.
        respuesta = requests.post(
            URL_OLLAMA, json=datos, timeout=60, stream=True
        )
        respuesta.raise_for_status()

        texto_acumulado = ""

        # Cada línea es un JSON con un token del modelo.
        # Formato: {"message":{"content":"token"},"done":false}
        for linea in respuesta.iter_lines(decode_unicode=True):
            if not linea:
                continue

            try:
                chunk = json.loads(linea)
            except json.JSONDecodeError:
                continue

            # ¿El modelo terminó de generar?
            if chunk.get("done", False):
                break

            # Extraer el token de este chunk.
            token = chunk.get("message", {}).get("content", "")
            texto_acumulado += token

            # --- Intento de parseo temprano ---
            # Después de cada token, verificamos si ya tenemos
            # un JSON completo. Si sí, retornamos INMEDIATAMENTE
            # sin esperar más tokens.
            # Esto es el truco que ahorra 200-500ms en comandos.
            resultado_temprano = _intentar_parseo_temprano(texto_acumulado)
            if resultado_temprano is not None:
                # ¡JSON completo! Guardar en historial y retornar.
                historial.append({"role": "assistant", "content": texto_acumulado})

                # Consumir el resto del stream en segundo plano
                # para que Ollama no se quede colgado.
                try:
                    for _ in respuesta.iter_lines():
                        pass
                except Exception:
                    pass

                return resultado_temprano

        # Si el stream terminó sin parseo temprano exitoso,
        # parseamos el texto completo normalmente.
        historial.append({"role": "assistant", "content": texto_acumulado})
        resultado = _parsear_respuesta(texto_acumulado)

        # Extracción de perfil si es conversación.
        if len(resultado) == 1 and resultado[0].get("comando") == "ninguno":
            _extraer_perfil_async(texto)

        return resultado

    except requests.ConnectionError:
        return [{"comando": "ninguno",
                 "respuesta": "No puedo conectar con Ollama. ¿Está corriendo?"}]
    except requests.Timeout:
        return [{"comando": "ninguno",
                 "respuesta": "Ollama tardó demasiado en responder."}]
    except Exception as error:
        return [{"comando": "ninguno",
                 "respuesta": f"Error inesperado: {error}"}]


def _intentar_parseo_temprano(texto):
    """
    Intenta parsear el texto acumulado como JSON completo.

    Se llama después de CADA token del stream. La mayoría de las
    veces falla (JSON incompleto) y retorna None. Pero en cuanto
    el JSON se cierra (el último "}" llega), lo parsea y retorna.

    Retorna:
        list: Lista de comandos parseados, o None si aún no está completo.
    """
    texto = texto.strip()

    # Limpiar bloques de pensamiento <think>...</think> que qwen3 genera.
    if "<think>" in texto:
        # Si el bloque de pensamiento aún no se cerró, esperar.
        if "</think>" not in texto:
            return None
        # Quitar el bloque de pensamiento completo.
        import re
        texto = re.sub(r"<think>.*?</think>", "", texto, flags=re.DOTALL).strip()

    # Necesitamos al menos un "{" para que sea JSON.
    if "{" not in texto:
        return None

    # Buscar el JSON.
    inicio = texto.find("{")
    fin = texto.rfind("}")

    # Si no hay "}" todavía, el JSON no está completo.
    if fin == -1 or fin <= inicio:
        return None

    json_texto = texto[inicio:fin + 1]

    # Verificar que los brackets estén balanceados.
    # Si hay más "{" que "}", el JSON está incompleto.
    if json_texto.count("{") != json_texto.count("}"):
        return None
    if json_texto.count("[") != json_texto.count("]"):
        return None

    try:
        resultado = json.loads(json_texto)
    except json.JSONDecodeError:
        return None  # Aún no es JSON válido, seguir esperando.

    # ¡JSON válido! Parsear y retornar.
    return _normalizar_resultado(resultado)


# ============================================================
# PARSEO Y NORMALIZACIÓN
# ============================================================

def _parsear_respuesta(texto_crudo):
    """Parsea la respuesta completa de Ollama. Fallback del streaming."""
    texto_limpio = texto_crudo.strip()

    # Limpiar bloques de pensamiento <think>...</think>.
    if "<think>" in texto_limpio and "</think>" in texto_limpio:
        import re
        texto_limpio = re.sub(r"<think>.*?</think>", "", texto_limpio, flags=re.DOTALL).strip()

    if "```" in texto_limpio:
        partes = texto_limpio.split("```")
        for parte in partes:
            parte = parte.strip()
            if parte.startswith("json"):
                parte = parte[4:].strip()
            if parte.startswith("{"):
                texto_limpio = parte
                break

    inicio = texto_limpio.find("{")
    fin = texto_limpio.rfind("}")

    if inicio == -1 or fin == -1 or fin <= inicio:
        return [{"comando": "ninguno", "respuesta": texto_crudo.strip()}]

    json_texto = texto_limpio[inicio:fin + 1]

    try:
        resultado = json.loads(json_texto)
    except json.JSONDecodeError:
        return [{"comando": "ninguno", "respuesta": texto_crudo.strip()}]

    return _normalizar_resultado(resultado)


def _normalizar_resultado(resultado):
    """
    Normaliza el resultado del JSON a una lista uniforme.
    Función compartida por parseo temprano y parseo completo.
    """
    # Formato 2: múltiples comandos.
    if "comandos" in resultado and isinstance(resultado["comandos"], list):
        lista = []
        for cmd in resultado["comandos"]:
            if isinstance(cmd, dict) and "comando" in cmd:
                if "parametros" not in cmd:
                    cmd["parametros"] = {}
                lista.append(cmd)
        if not lista:
            return [{"comando": "ninguno", "respuesta": str(resultado)}]
        return lista[:5]

    # Formato 1 y 3: comando único o conversación.
    if "comando" not in resultado:
        return [{"comando": "ninguno", "respuesta": str(resultado)}]

    if "parametros" not in resultado:
        resultado["parametros"] = {}

    # Manejar JSON anidado accidental.
    if "respuesta" in resultado:
        resp = resultado["respuesta"]
        if isinstance(resp, str) and resp.strip().startswith("{"):
            try:
                inner = json.loads(resp)
                if "respuesta" in inner:
                    resultado["respuesta"] = inner["respuesta"]
            except (json.JSONDecodeError, TypeError):
                pass

    if resultado["comando"] == "ninguno" and "respuesta" not in resultado:
        resultado["respuesta"] = "(sin respuesta)"

    return [resultado]


# ============================================================
# MEMORIA
# ============================================================

def generar_resumen_sesion():
    """Genera un resumen de la sesión y lo guarda en memoria."""
    global _memoria
    if _memoria is None:
        return ""

    mensajes_sesion = [m for m in historial if m["role"] in ("user", "assistant")]
    if len(mensajes_sesion) < 4:
        return ""

    mensajes_recientes = mensajes_sesion[-20:]
    conversacion = ""
    for m in mensajes_recientes:
        rol = "Usuario" if m["role"] == "user" else "Eli"
        conversacion += f"{rol}: {m['content']}\n"

    prompt_resumen = [
        {"role": "system", "content": (
            "Resume esta conversación en 2-3 oraciones cortas. "
            "Enfócate en: qué pidió el usuario, datos personales, temas tocados. "
            "Responde SOLO el resumen."
        )},
        {"role": "user", "content": conversacion}
    ]

    try:
        respuesta = requests.post(
            URL_OLLAMA,
            json={"model": MODELO, "messages": prompt_resumen, "stream": False},
            timeout=30
        )
        respuesta.raise_for_status()
        resumen = respuesta.json()["message"]["content"].strip()
        agregar_resumen(_memoria, resumen)
        guardar_memoria(_memoria)
        print(f"🧠 Resumen guardado: {resumen[:80]}...")
        return resumen
    except Exception as error:
        print(f"⚠️ No pude generar resumen: {error}")
        return ""


def _extraer_perfil_async(texto_usuario):
    """Extrae datos personales del texto del usuario."""
    global _memoria
    prompt_extraccion = [
        {"role": "system", "content": (
            "Analiza este mensaje y extrae SOLO datos personales del usuario. "
            "Responde SOLO un JSON. Si no hay datos, responde: {}\n"
            '"me llamo Paolo" → {"nombre": "Paolo"}\n'
            '"qué hora es" → {}'
        )},
        {"role": "user", "content": texto_usuario}
    ]
    try:
        respuesta = requests.post(
            URL_OLLAMA,
            json={"model": MODELO, "messages": prompt_extraccion, "stream": False},
            timeout=15
        )
        respuesta.raise_for_status()
        texto = respuesta.json()["message"]["content"].strip()
        # Limpiar <think> blocks
        if "<think>" in texto and "</think>" in texto:
            import re
            texto = re.sub(r"<think>.*?</think>", "", texto, flags=re.DOTALL).strip()
        inicio = texto.find("{")
        fin = texto.rfind("}")
        if inicio == -1 or fin == -1:
            return
        datos = json.loads(texto[inicio:fin + 1])
        if datos:
            actualizar_perfil(_memoria, datos)
            guardar_memoria(_memoria)
            print(f"   🧠 Perfil actualizado: {datos}")
    except Exception:
        pass


def _construir_system_prompt(texto_memoria):
    """Construye el system prompt inyectando memoria y comandos."""
    if not texto_memoria:
        texto_memoria = "No hay datos previos del usuario. Primera sesión."
    prompt = _SYSTEM_PROMPT_BASE.replace("{MEMORIA_USUARIO}", texto_memoria)
    prompt += _SYSTEM_PROMPT_TECNICO.replace("{COMANDOS}", COMANDOS_DISPONIBLES)
    return prompt


def limpiar_historial():
    """Borra la conversación pero mantiene la memoria."""
    global _memoria
    if _memoria is None:
        _memoria = cargar_memoria()
    texto_memoria = memoria_a_texto(_memoria)
    system_prompt = _construir_system_prompt(texto_memoria)
    historial.clear()
    historial.append({"role": "system", "content": system_prompt})


def obtener_memoria():
    """Retorna la memoria actual."""
    global _memoria
    if _memoria is None:
        _memoria = cargar_memoria()
    return _memoria


# --- Prueba directa ---
if __name__ == "__main__":
    import time

    print("=== Prueba del cerebro optimizado ===\n")
    inicializar()
    print('Escribe algo (o "salir").\n')

    while True:
        entrada = input("Tú: ").strip()
        if not entrada:
            continue
        if entrada.lower() == "salir":
            break

        inicio = time.time()
        resultados = pensar(entrada)
        elapsed = time.time() - inicio

        print(f"  [JSON] {json.dumps(resultados, ensure_ascii=False)}")
        print(f"  ⏱️ {elapsed:.2f}s | Comandos: {len(resultados)}")

        for i, r in enumerate(resultados):
            if r["comando"] != "ninguno":
                params = r.get("parametros", {})
                params_txt = f" → {params}" if params else ""
                print(f"  [{i+1}] {r['comando']}{params_txt}")
            else:
                print(f"  Eli: {r.get('respuesta', '(sin respuesta)')}")
        print()

    print("\nGenerando resumen...")
    generar_resumen_sesion()
