# ============================================================
# pc_control.py — Control del PC para Eli (con Spotify API)
# Recibe nombre de comando + parámetros desde Ollama vía JSON.
# ============================================================

import subprocess
import webbrowser
import pyautogui
import psutil
import datetime
import os
import urllib.parse
import threading
import requests
import shutil
import glob
from blackboard_commands import listar_mis_cursos, abrir_curso

from logger import get_logger
import os_compat

log = get_logger(__name__)


# --- Importar control de Spotify ---
# Usamos try/except porque si spotipy no está instalado o las
# credenciales no están configuradas, Eli sigue funcionando
# para todo lo demás. Solo los comandos de Spotify fallarían.
try:
    import spotify_control
    SPOTIFY_DISPONIBLE = True
except Exception as error:
    SPOTIFY_DISPONIBLE = False
    log.warning("Spotify no disponible: %s. Los demás comandos siguen funcionando.", error)

try:
    import google_calendar
    CALENDAR_DISPONIBLE = True
except Exception as error:
    CALENDAR_DISPONIBLE = False
    log.warning("Google Calendar no disponible: %s", error)

try:
    import gmail
    GMAIL_DISPONIBLE = True
except Exception as error:
    GMAIL_DISPONIBLE = False
    log.warning("Gmail no disponible: %s", error)


# --- Temporizador ---
_temporizador_activo = None
_funcion_hablar = None


def configurar_voz(funcion_hablar):
    global _funcion_hablar
    _funcion_hablar = funcion_hablar


def ejecutar_comando(nombre, parametros):
    """
    Ejecuta un comando del PC por su nombre.

    Args:
        nombre (str): Nombre del comando desde Ollama.
        parametros (dict): Parámetros extraídos por Ollama.

    Retorna:
        str: Texto para que Eli diga, o None si el comando no existe.
    """
    funcion = DISPATCH.get(nombre)
    if funcion is None:
        return None
    return funcion(parametros)


def _calendar_check():
    """Verifica que google_calendar esté disponible."""
    if not CALENDAR_DISPONIBLE:
        return "Google Calendar no está configurado. Revisa credentials.json."
    return None


def _calendario_hoy(params):
    """Eventos de hoy."""
    error = _calendar_check()
    if error:
        return error
    return google_calendar.ver_eventos_hoy()


def _calendario_manana(params):
    """Eventos de mañana."""
    error = _calendar_check()
    if error:
        return error
    return google_calendar.ver_eventos_manana()


def _calendario_semana(params):
    """Eventos de los próximos 7 días."""
    error = _calendar_check()
    if error:
        return error
    dias = params.get("dias", 7)
    try:
        dias = int(dias)
    except (ValueError, TypeError):
        dias = 7
    return google_calendar.proximos_eventos(dias)


def _crear_evento_calendario(params):
    """
    Crea un evento. Ollama envía:
    {
        "titulo": "Reunión con cliente",
        "fecha": "2025-07-15",
        "hora": "15:00",
        "duracion": 60
    }
    """
    error = _calendar_check()
    if error:
        return error

    titulo = params.get("titulo", "")
    fecha = params.get("fecha", "")
    hora = params.get("hora", "")
    duracion = params.get("duracion", 60)

    if not titulo:
        return "¿Cómo se llama el evento?"
    if not fecha:
        return "¿Qué día es el evento? Necesito la fecha."
    if not hora:
        return "¿A qué hora es el evento?"

    try:
        duracion = int(duracion)
    except (ValueError, TypeError):
        duracion = 60

    return google_calendar.crear_evento(titulo, fecha, hora, duracion)


def _buscar_evento_calendario(params):
    """
    Busca eventos por nombre.
    Ollama envía: {"busqueda": "reunión"}
    """
    error = _calendar_check()
    if error:
        return error

    busqueda = params.get("busqueda", "")
    if not busqueda:
        return "¿Qué evento quieres buscar?"

    return google_calendar.buscar_evento(busqueda)



# ============================================================
# GMAIL
# ============================================================

def _gmail_check():
    if not GMAIL_DISPONIBLE:
        return "Gmail no está configurado."
    return None


def _gmail_no_leidos(params):
    error = _gmail_check()
    if error:
        return error
    return gmail.contar_no_leidos()


def _gmail_recientes(params):
    error = _gmail_check()
    if error:
        return error
    cantidad = params.get("cantidad", 5)
    try:
        cantidad = int(cantidad)
    except (ValueError, TypeError):
        cantidad = 5
    return gmail.leer_emails_recientes(cantidad)


def _gmail_importantes(params):
    error = _gmail_check()
    if error:
        return error
    return gmail.leer_email_importante()


def _gmail_buscar(params):
    error = _gmail_check()
    if error:
        return error
    busqueda = params.get("busqueda", "")
    if not busqueda:
        return "¿Qué email quieres buscar?"
    return gmail.buscar_email(busqueda)


def _gmail_enviar(params):
    error = _gmail_check()
    if error:
        return error
    destinatario = params.get("destinatario", "")
    asunto = params.get("asunto", "")
    cuerpo = params.get("cuerpo", "")
    if not destinatario:
        return "¿A quién quieres enviar el email? Necesito la dirección."
    if not asunto:
        asunto = "Mensaje de Eli"
    if not cuerpo:
        return "¿Qué quieres que diga el email?"
    return gmail.enviar_email(destinatario, asunto, cuerpo)


# ============================================================
# ABRIR PROGRAMAS
# ============================================================

def _abrir_app_simple(nombre_logico, mensaje_ok, mensaje_falla):
    """Helper común: invoca os_compat.abrir_app y retorna mensaje."""
    if os_compat.abrir_app(nombre_logico):
        return mensaje_ok
    return mensaje_falla


def _abrir_chrome(params):
    return _abrir_app_simple(
        "chrome", "Abriendo Chrome.",
        "No encontré Chrome instalado.",
    )

def _abrir_notepad(params):
    return _abrir_app_simple(
        "notepad", "Abriendo el editor de texto.",
        "No encontré un editor de texto instalado.",
    )

def _abrir_calculadora(params):
    return _abrir_app_simple(
        "calculadora", "Abriendo la calculadora.",
        "No encontré una calculadora instalada.",
    )

def _abrir_explorador(params):
    return _abrir_app_simple(
        "explorador", "Abriendo el explorador de archivos.",
        "No pude abrir el explorador.",
    )

def _abrir_configuracion(params):
    return _abrir_app_simple(
        "configuracion", "Abriendo la configuración.",
        "No encontré la configuración del sistema.",
    )

def _abrir_word(params):
    return _abrir_app_simple(
        "word", "Abriendo Word.",
        "No encontré Word ni LibreOffice Writer.",
    )

def _abrir_excel(params):
    return _abrir_app_simple(
        "excel", "Abriendo Excel.",
        "No encontré Excel ni LibreOffice Calc.",
    )

def _abrir_powerpoint(params):
    return _abrir_app_simple(
        "powerpoint", "Abriendo PowerPoint.",
        "No encontré PowerPoint ni LibreOffice Impress.",
    )

def _abrir_spotify(params):
    import time
    if os_compat.abrir_app("spotify"):
        time.sleep(3)  # Esperar a que Spotify inicie
        return "Abriendo Spotify. Dame un momento para que cargue."
    return "No encontré Spotify instalado."


# ============================================================
# VOLUMEN DEL SISTEMA
# ============================================================

def _subir_volumen(params):
    for _ in range(5):
        pyautogui.press("volumeup")
    return "Volumen subido."

def _bajar_volumen(params):
    for _ in range(5):
        pyautogui.press("volumedown")
    return "Volumen bajado."

def _silenciar(params):
    pyautogui.press("volumemute")
    return "Audio silenciado."

def _volumen_especifico(params):
    porcentaje = params.get("porcentaje", 50)
    try:
        porcentaje = int(porcentaje)
    except (ValueError, TypeError):
        porcentaje = 50
    porcentaje = max(0, min(100, porcentaje))
    for _ in range(50):
        pyautogui.press("volumedown")
    for _ in range(porcentaje // 2):
        pyautogui.press("volumeup")
    return f"Volumen del sistema al {porcentaje}%."


# ============================================================
# SPOTIFY (API oficial)
# Estas funciones son wrappers que llaman a spotify_control.py.
# Cada una verifica primero si Spotify está disponible.
# ============================================================

def _spotify_check():
    """Verifica que spotify_control esté importado correctamente."""
    if not SPOTIFY_DISPONIBLE:
        return "Spotify no está configurado. Revisa las credenciales en spotify_control.py."
    return None  # None = todo bien, seguir adelante.

def _spotify_play(params):
    """Reanudar reproducción."""
    error = _spotify_check()
    if error:
        return error
    return spotify_control.play()

def _spotify_pause(params):
    """Pausar reproducción."""
    error = _spotify_check()
    if error:
        return error
    return spotify_control.pause()

def _spotify_siguiente(params):
    """Siguiente canción."""
    error = _spotify_check()
    if error:
        return error
    return spotify_control.siguiente()

def _spotify_anterior(params):
    """Canción anterior."""
    error = _spotify_check()
    if error:
        return error
    return spotify_control.anterior()

def _spotify_volumen(params):
    """
    Cambia el volumen de Spotify (no del sistema).
    Ollama envía: {"porcentaje": 70}
    """
    error = _spotify_check()
    if error:
        return error
    porcentaje = params.get("porcentaje", 50)
    return spotify_control.volumen(porcentaje)

def _spotify_que_suena(params):
    """Dice qué canción está sonando."""
    error = _spotify_check()
    if error:
        return error
    return spotify_control.que_suena()

def _spotify_buscar(params):
    """
    Busca y reproduce una canción en Spotify.
    Ollama envía: {"busqueda": "Blinding Lights"}
    """
    error = _spotify_check()
    if error:
        return error
    busqueda = params.get("busqueda", "")
    if not busqueda:
        return "No entendí qué canción quieres escuchar."
    return spotify_control.buscar_y_reproducir(busqueda)


def _spotify_playlist(params):
    busqueda = params.get("busqueda", "")
    if not busqueda:
        return "¿Qué playlist quieres reproducir?"
    return spotify_control.buscar_y_reproducir_playlist(busqueda)


# ============================================================
# PANTALLA
# ============================================================

def _captura_pantalla(params):
    ahora = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    ruta = str(os_compat.DESKTOP / f"captura_{ahora}.png")
    pyautogui.screenshot(ruta)
    return "Captura guardada en el escritorio."

def _bloquear_pantalla(params):
    if os_compat.bloquear_pantalla():
        return "Bloqueando la pantalla."
    return "No pude bloquear la pantalla."


# ============================================================
# FECHA, HORA, CLIMA
# ============================================================

def _decir_hora(params):
    ahora = datetime.datetime.now()
    return f"Son las {ahora.strftime('%I:%M %p')}."

def _decir_fecha(params):
    ahora = datetime.datetime.now()
    dias = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"]
    meses = [
        "enero", "febrero", "marzo", "abril", "mayo", "junio",
        "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre"
    ]
    return (
        f"Hoy es {dias[ahora.weekday()]} {ahora.day} "
        f"de {meses[ahora.month - 1]} de {ahora.year}."
    )

def _consultar_clima(params):
    ciudad = params.get("ciudad", "")
    if not ciudad:
        return "No entendí de qué ciudad quieres saber el clima."
    try:
        url = (
            f"https://wttr.in/{urllib.parse.quote(ciudad)}"
            f"?format=%C,+%t,+humedad+%h,+viento+%w&lang=es"
        )
        resp = requests.get(url, timeout=5)
        if resp.status_code == 200 and "Unknown" not in resp.text:
            return f"El clima en {ciudad}: {resp.text.strip()}."
        return f"No encontré información del clima para {ciudad}."
    except requests.ConnectionError:
        return "No pude consultar el clima. Verifica tu conexión."
    except Exception:
        return "Hubo un error al consultar el clima."


# ============================================================
# BATERÍA Y SISTEMA
# ============================================================

def _bateria(params):
    bateria = psutil.sensors_battery()
    if bateria is None:
        return "No detecté una batería."
    porcentaje = int(bateria.percent)
    cargando = " y cargando" if bateria.power_plugged else ""
    return f"La batería está al {porcentaje}%{cargando}."

def _apagar_pc(params):
    if os_compat.apagar_pc(60):
        return "La computadora se apagará en 60 segundos. Di cancelar apagado para detenerlo."
    return "No pude programar el apagado."

def _cancelar_apagado(params):
    if os_compat.cancelar_apagado():
        return "Apagado cancelado."
    return "No había un apagado programado o no pude cancelarlo."

def _vaciar_papelera(params):
    if os_compat.vaciar_papelera():
        return "Papelera vaciada."
    return "No pude vaciar la papelera."

def _modo_oscuro(params):
    nuevo_modo = os_compat.modo_oscuro_toggle()
    if nuevo_modo:
        return f"Modo {nuevo_modo} activado."
    return "No pude cambiar el tema del sistema."


# ============================================================
# TEMPORIZADOR
# ============================================================

def _poner_temporizador(params):
    global _temporizador_activo
    cantidad = params.get("cantidad", 0)
    unidad = params.get("unidad", "minutos").lower()
    try:
        cantidad = int(cantidad)
    except (ValueError, TypeError):
        return "No entendí la cantidad del temporizador."
    if cantidad <= 0:
        return "La cantidad debe ser mayor a cero."
    if "segundo" in unidad:
        segundos = cantidad
    elif "hora" in unidad:
        segundos = cantidad * 3600
    else:
        segundos = cantidad * 60
    unidad_limpia = unidad.rstrip("s")
    texto_tiempo = f"{cantidad} {unidad_limpia}" + ("s" if cantidad != 1 else "")
    if _temporizador_activo and _temporizador_activo.is_alive():
        _temporizador_activo.cancel()
    _temporizador_activo = threading.Timer(
        segundos, _temporizador_terminado, args=[texto_tiempo]
    )
    _temporizador_activo.daemon = True
    _temporizador_activo.start()
    return f"Temporizador de {texto_tiempo} iniciado."

def _cancelar_temporizador(params):
    global _temporizador_activo
    if _temporizador_activo and _temporizador_activo.is_alive():
        _temporizador_activo.cancel()
        _temporizador_activo = None
        return "Temporizador cancelado."
    return "No hay ningún temporizador activo."

def _temporizador_terminado(texto_tiempo):
    mensaje = f"¡Tiempo! El temporizador de {texto_tiempo} ha terminado."
    log.info("⏰ %s", mensaje)
    if _funcion_hablar:
        _funcion_hablar(mensaje)


# ============================================================
# BÚSQUEDAS WEB
# ============================================================

def _buscar_google(params):
    busqueda = params.get("busqueda", "")
    if not busqueda:
        return "No entendí qué quieres buscar."
    webbrowser.open(f"https://www.google.com/search?q={urllib.parse.quote(busqueda)}")
    return f"Buscando {busqueda} en Google."

def _abrir_youtube(params):
    webbrowser.open("https://www.youtube.com")
    return "Abriendo YouTube."

def _buscar_youtube(params):
    busqueda = params.get("busqueda", "")
    if not busqueda:
        return "No entendí qué quieres buscar."
    webbrowser.open(
        f"https://www.youtube.com/results?search_query={urllib.parse.quote(busqueda)}"
    )
    return f"Buscando {busqueda} en YouTube."

# ============================================================
# ABRIR PROGRAMAS DE INGENIERÍA
# ============================================================
# Estrategia: primero intentamos shutil.which() que busca el
# ejecutable en el PATH del sistema. Si no lo encuentra, probamos
# rutas comunes donde se instalan estos programas.
# Si ninguna funciona, avisamos al usuario.

# Rutas conocidas donde se instalan los programas.
# Cada programa tiene una lista de rutas posibles porque
# las versiones cambian la carpeta (2024, 2025, etc.).
# glob permite usar comodines (*) para cubrir varias versiones.

# AutoCAD/Civil 3D/ArcGIS son productos solo Windows. En Linux
# shutil.which fallará y la función reportará "no encontré".
# QGIS sí corre en Linux (paquete `qgis` en Ubuntu).
RUTAS_AUTOCAD = [
    r"C:\Program Files\Autodesk\AutoCAD*\acad.exe",
]

RUTAS_CIVIL3D = [
    r"C:\Program Files\Autodesk\AutoCAD*\acad.exe",
]

RUTAS_QGIS = [
    r"C:\Program Files\QGIS*\bin\qgis-bin.exe",
    r"C:\Program Files\QGIS*\bin\qgis.bat",
    r"C:\OSGeo4W\bin\qgis.bat",
    "/usr/bin/qgis",
    "/usr/local/bin/qgis",
]

RUTAS_ARCGIS = [
    r"C:\Program Files\ArcGIS\Pro\bin\ArcGISPro.exe",
    r"C:\Program Files (x86)\ArcGIS\Desktop*\bin\ArcMap.exe",
]


def _buscar_ejecutable(nombre_comando, rutas_conocidas):
    """
    Busca un ejecutable: primero en el PATH, luego en rutas conocidas.

    shutil.which() busca en todas las carpetas del PATH del sistema.
    Si el programa se agregó al PATH durante la instalación, lo encuentra.
    Si no, probamos rutas comunes con glob (que acepta comodines *).

    Args:
        nombre_comando (str): Nombre del ejecutable (ej: "acad").
        rutas_conocidas (list): Lista de rutas con comodines.

    Retorna:
        str: Ruta completa al ejecutable, o None si no lo encontró.
    """
    import shutil
    import glob

    # Intento 1: buscar en el PATH del sistema.
    ruta = shutil.which(nombre_comando)
    if ruta:
        return ruta

    # Intento 2: buscar en rutas conocidas con comodines.
    # glob.glob() expande "C:\Program Files\QGIS*\bin\qgis-bin.exe"
    # a todas las carpetas que coincidan (QGIS 3.34, QGIS 3.36, etc.).
    for patron in rutas_conocidas:
        resultados = glob.glob(patron)
        if resultados:
            # Tomar el más reciente (último alfabéticamente = versión más nueva).
            resultados.sort()
            return resultados[-1]

    return None


def _abrir_autocad(params):
    """Abre AutoCAD buscando el ejecutable automáticamente."""
    ruta = _buscar_ejecutable("acad", RUTAS_AUTOCAD)
    if ruta:
        subprocess.Popen([ruta])
        return "Abriendo AutoCAD."
    return "No encontré AutoCAD instalado. Verifica la instalación."


def _abrir_civil3d(params):
    """
    Abre Civil 3D.
    Civil 3D se instala como un perfil de AutoCAD. El ejecutable
    es el mismo (acad.exe) pero con un perfil distinto.
    Si Civil 3D está instalado, busca su acceso directo primero.
    """
    # Intentar el acceso directo del menú inicio primero.
    resultado = os.system('start "" "Civil 3D"')
    if resultado == 0:
        return "Abriendo Civil 3D."

    # Fallback: abrir AutoCAD (Civil 3D es AutoCAD con extensiones).
    ruta = _buscar_ejecutable("acad", RUTAS_CIVIL3D)
    if ruta:
        subprocess.Popen([ruta])
        return "Abriendo AutoCAD con Civil 3D."
    return "No encontré Civil 3D instalado. Verifica la instalación."


def _abrir_qgis(params):
    """Abre QGIS buscando el ejecutable automáticamente."""
    ruta = _buscar_ejecutable("qgis", RUTAS_QGIS)
    if ruta:
        subprocess.Popen([ruta])
        return "Abriendo QGIS."

    # Fallback: intentar por el menú inicio.
    resultado = os.system('start "" "QGIS"')
    if resultado == 0:
        return "Abriendo QGIS."
    return "No encontré QGIS instalado. Verifica la instalación."


def _abrir_arcgis(params):
    """Abre ArcGIS Pro buscando el ejecutable automáticamente."""
    ruta = _buscar_ejecutable("ArcGISPro", RUTAS_ARCGIS)
    if ruta:
        subprocess.Popen([ruta])
        return "Abriendo ArcGIS."

    resultado = os.system('start "" "ArcGIS Pro"')
    if resultado == 0:
        return "Abriendo ArcGIS Pro."
    return "No encontré ArcGIS instalado. Verifica la instalación."


# ============================================================
# MANEJO DE ARCHIVOS
# ============================================================

# Carpeta de proyectos: resuelta por SO en os_compat (en Linux es
# ~/Escritorio/Carpeta proyectos, en Windows la ruta histórica).
CARPETA_PROYECTOS = str(os_compat.CARPETA_PROYECTOS)


def _abrir_carpeta_proyectos(params):
    """Abre la carpeta de proyectos en el explorador."""
    carpeta = params.get("carpeta", CARPETA_PROYECTOS)

    if os.path.exists(carpeta):
        if os_compat.abrir_path(carpeta):
            return "Abriendo carpeta de proyectos."
        return "No pude abrir la carpeta de proyectos."

    # Si no existe, la creamos y la abrimos.
    try:
        os.makedirs(carpeta, exist_ok=True)
        if os_compat.abrir_path(carpeta):
            return "Creé y abrí la carpeta de proyectos."
        return "Creé la carpeta pero no pude abrirla."
    except OSError:
        return "No pude abrir la carpeta de proyectos."


def _abrir_en_carpeta(params):
    """Abre el explorador en una carpeta del usuario.

    Ollama envía: {"carpeta": "documentos"} o {"carpeta": "descargas"}.
    Las rutas vienen de os_compat (resueltas por SO y locale).
    """
    destino = params.get("carpeta", "documentos").lower()

    carpetas = {
        "documentos": os_compat.DOCUMENTS,
        "descargas":  os_compat.DOWNLOADS,
        "escritorio": os_compat.DESKTOP,
        "imágenes":   os_compat.PICTURES,
        "imagenes":   os_compat.PICTURES,
        "videos":     os_compat.VIDEOS,
        "vídeos":     os_compat.VIDEOS,
        "música":     os_compat.MUSIC,
        "musica":     os_compat.MUSIC,
        "proyectos":  os_compat.CARPETA_PROYECTOS,
    }

    ruta = carpetas.get(destino)

    if ruta and os.path.exists(str(ruta)):
        if os_compat.abrir_path(ruta):
            return f"Abriendo la carpeta de {destino}."

    # Si no es un nombre conocido, intentar como ruta directa.
    if os.path.exists(destino):
        if os_compat.abrir_path(destino):
            return f"Abriendo {destino}."

    return f"No encontré la carpeta '{destino}'."


def _buscar_archivos(params):
    """
    Busca archivos por extensión en la carpeta de proyectos.
    Ollama envía: {"extension": "dwg"} o {"extension": "shp"}

    Usa glob para buscar recursivamente (**) en la carpeta de proyectos.
    Retorna cuántos encontró y los primeros 5 nombres.
    """
    import glob

    extension = params.get("extension", "").strip().lstrip(".")

    if not extension:
        return "¿Qué tipo de archivos quieres buscar? Dime la extensión, por ejemplo DWG o SHP."

    # Buscar recursivamente en la carpeta de proyectos.
    # ** significa "cualquier subcarpeta a cualquier nivel".
    patron = os.path.join(CARPETA_PROYECTOS, "**", f"*.{extension}")
    archivos = glob.glob(patron, recursive=True)

    if not archivos:
        return f"No encontré archivos .{extension} en la carpeta de proyectos."

    # Mostrar los primeros 5 para no hacer la respuesta eterna.
    total = len(archivos)
    muestra = archivos[:5]
    nombres = [os.path.basename(a) for a in muestra]
    lista = ", ".join(nombres)

    if total <= 5:
        return f"Encontré {total} archivos .{extension}: {lista}."
    else:
        return f"Encontré {total} archivos .{extension}. Los primeros: {lista}."


def _crear_carpeta(params):
    """
    Crea una nueva carpeta dentro de la carpeta de proyectos.
    Ollama envía: {"nombre": "Proyecto Puente Norte"}
    """
    nombre = params.get("nombre", "").strip()

    if not nombre:
        return "¿Cómo quieres que se llame la carpeta?"

    # Limpiar caracteres no válidos para nombres de carpeta en Windows.
    # Windows no permite: \ / : * ? " < > |
    caracteres_invalidos = r'\/:*?"<>|'
    for c in caracteres_invalidos:
        nombre = nombre.replace(c, "")

    ruta = os.path.join(CARPETA_PROYECTOS, nombre)

    if os.path.exists(ruta):
        return f"La carpeta '{nombre}' ya existe."

    try:
        os.makedirs(ruta, exist_ok=True)
        return f"Carpeta '{nombre}' creada en proyectos."
    except OSError as error:
        return f"No pude crear la carpeta: {error}"


# ============================================================
# UTILIDADES DE INGENIERÍA
# ============================================================

def _calculadora_cientifica(params):
    """Abre la calculadora en modo científico cuando es posible.

    En Windows manda Alt+2 después de abrir calc (shortcut de la
    calculadora moderna para "modo científico"). En Linux no hay
    shortcut universal, así que solo abrimos la calculadora.
    """
    import time
    if not os_compat.abrir_app("calculadora"):
        return "No encontré una calculadora instalada."

    if os_compat.IS_WINDOWS:
        time.sleep(1)
        pyautogui.hotkey("alt", "2")
        return "Abriendo calculadora científica."
    return "Abriendo calculadora."


def _convertir_unidades(params):
    """
    Abre un conversor de unidades en el navegador.
    Google tiene un conversor integrado que funciona perfecto.
    """
    tipo = params.get("tipo", "")
    if tipo:
        webbrowser.open(
            f"https://www.google.com/search?q=convertir+{urllib.parse.quote(tipo)}"
        )
        return f"Abriendo conversor de {tipo}."
    else:
        webbrowser.open("https://www.google.com/search?q=conversor+de+unidades")
        return "Abriendo conversor de unidades."

# ============================================================
# DISPATCH TABLE
# ============================================================

DISPATCH = {
    # Abrir programas
    "abrir_chrome":           _abrir_chrome,
    "abrir_notepad":          _abrir_notepad,
    "abrir_calculadora":      _abrir_calculadora,
    "abrir_explorador":       _abrir_explorador,
    "abrir_configuracion":    _abrir_configuracion,
    "abrir_word":             _abrir_word,
    "abrir_excel":            _abrir_excel,
    "abrir_powerpoint":       _abrir_powerpoint,
    "abrir_spotify":          _abrir_spotify,
    "abrir_youtube":          _abrir_youtube,

    # Volumen del sistema
    "subir_volumen":          _subir_volumen,
    "bajar_volumen":          _bajar_volumen,
    "silenciar":              _silenciar,
    "volumen_especifico":     _volumen_especifico,
    

    # Spotify (API oficial)
    "spotify_play":           _spotify_play,
    "spotify_pause":          _spotify_pause,
    "spotify_siguiente":      _spotify_siguiente,
    "spotify_anterior":       _spotify_anterior,
    "spotify_volumen":        _spotify_volumen,
    "spotify_que_suena":      _spotify_que_suena,
    "spotify_reproducir":     _spotify_buscar,
    "spotify_playlist":       _spotify_playlist,
    "spotify_buscar":         _spotify_buscar,

    # Comandos Blackboard
    "listar_cursos":          lambda p: listar_mis_cursos(),
    "abrir_curso":            lambda p: abrir_curso(p.get("parametros", {}).get("nombre_curso", "")),

    # Pantalla
    "captura_pantalla":       _captura_pantalla,
    "bloquear_pantalla":      _bloquear_pantalla,

    # Info
    "dejar_hora":             _decir_hora,
    "decir_hora_actual":      _decir_hora,
    "consultar_clima":        _consultar_clima,
    "bateria":                _bateria,
    "decir_fecha":            _decir_fecha,

    # Sistema
    "poner_temporizador":     _poner_temporizador,
    "cancelar_temporizador":  _cancelar_temporizador,
    "vaciar_papelera":        _vaciar_papelera,
    "modo_oscuro":            _modo_oscuro,
    "apagar_pc":              _apagar_pc,
    "cancelar_apagado":       _cancelar_apagado,

    # Búsquedas
    "buscar_google":          _buscar_google,
    "buscar_youtube":         _buscar_youtube,

    # Ingeniería — Programas
    "abrir_autocad":          _abrir_autocad,
    "abrir_civil3d":          _abrir_civil3d,
    "abrir_qgis":             _abrir_qgis,
    "abrir_arcgis":           _abrir_arcgis,

    # Ingeniería — Archivos
    "abrir_carpeta_proyectos": _abrir_carpeta_proyectos,
    "abrir_en_carpeta":       _abrir_en_carpeta,
    "buscar_archivos":        _buscar_archivos,
    "crear_carpeta":          _crear_carpeta,

    # Ingeniería — Utilidades
    "calculadora_cientifica": _calculadora_cientifica,
    "convertir_unidades":     _convertir_unidades,

    # Google Calendar
    "calendario_hoy":          _calendario_hoy,
    "calendario_manana":       _calendario_manana,
    "calendario_semana":       _calendario_semana,
    "crear_evento_calendario": _crear_evento_calendario,
    "buscar_evento_calendario": _buscar_evento_calendario,

    # Gmail
    "gmail_no_leidos":         _gmail_no_leidos,
    "gmail_recientes":         _gmail_recientes,
    "gmail_importantes":       _gmail_importantes,
    "gmail_buscar":            _gmail_buscar,
    "gmail_enviar":            _gmail_enviar,
}


# --- Prueba directa ---
if __name__ == "__main__":
    print("=== Prueba de comandos ===\n")

    pruebas = [
        ("spotify_que_suena", {}),
        ("spotify_buscar", {"busqueda": "Bohemian Rhapsody"}),
        ("spotify_volumen", {"porcentaje": 60}),
        ("decir_hora", {}),
        ("comando_falso", {}),
    ]

    for nombre, params in pruebas:
        resultado = ejecutar_comando(nombre, params)
        estado = resultado if resultado else "(comando no existe)"
        print(f"  {nombre} → {estado}")
