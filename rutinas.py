# ============================================================
# rutinas.py — Sistema de rutinas automáticas para Eli
#
# 3 tipos de rutinas:
#
# 1. SALUDO AUTOMÁTICO: al iniciar Eli, saluda según la hora,
#    dice el clima y una frase motivacional con personalidad.
#
# 2. RUTINAS PROGRAMADAS: el usuario las crea con voz y se
#    ejecutan automáticamente a la hora indicada.
#    Se guardan en rutinas.json para persistir entre sesiones.
#
# 3. RUTINAS MANUALES: el usuario dice "ejecuta rutina mañana"
#    y se ejecutan los comandos guardados de esa rutina.
# ============================================================

from __future__ import annotations

import json
import os
import datetime
import threading
import time
from typing import Any, Callable

import config as cfg
from logger import get_logger

log = get_logger(__name__)

# --- Archivo de rutinas ---
# Se guarda en la misma carpeta que Eli.
RUTA_RUTINAS = os.path.join(os.path.dirname(__file__), "rutinas.json")

# Ciudad para el clima del saludo (override con ELI_CIUDAD_CLIMA).
CIUDAD_CLIMA = cfg.CIUDAD_CLIMA


# ============================================================
# 1. SALUDO AUTOMÁTICO
# ============================================================

def ejecutar_saludo(
    hablar_fn: Callable[[str], None],
    pensar_fn: Callable[..., list[dict[str, Any]]],
    clima_fn: Callable[[dict[str, Any]], str],
) -> None:
    """Saludo minimalista al iniciar Eli.

    Emite un mensaje corto y directo estilo Agnes Tachyon.

    Args:
        hablar_fn: Función hablar() de Eli.
        pensar_fn: No usado (mantenido por compatibilidad).
        clima_fn: No usado (mantenido por compatibilidad).
    """
    hablar_fn("Sistemas operativos. Esperando directivas.")


# ============================================================
# 2. GESTIÓN DE RUTINAS (CRUD)
# ============================================================

def cargar_rutinas() -> dict[str, dict[str, Any]]:
    """
    Lee rutinas.json y retorna el diccionario de rutinas.

    Estructura del archivo:
    {
        "mañana": {
            "nombre": "mañana",
            "hora": "07:00",
            "comandos": [
                {"comando": "abrir_autocad", "parametros": {}},
                {"comando": "spotify_playlist", "parametros": {"busqueda": "trabajo"}}
            ],
            "activa": true
        },
        "noche": {
            "nombre": "noche",
            "hora": "22:00",
            "comandos": [
                {"comando": "spotify_pause", "parametros": {}},
                {"comando": "silenciar", "parametros": {}}
            ],
            "activa": true
        }
    }
    """
    if not os.path.exists(RUTA_RUTINAS):
        return {}

    try:
        with open(RUTA_RUTINAS, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError):
        log.warning("rutinas.json corrupto. Creando archivo nuevo.")
        return {}


def guardar_rutinas(rutinas: dict[str, dict[str, Any]]) -> None:
    """Guarda el diccionario de rutinas en rutinas.json."""
    try:
        with open(RUTA_RUTINAS, "w", encoding="utf-8") as f:
            json.dump(rutinas, f, indent=2, ensure_ascii=False)
    except IOError as error:
        log.warning("No pude guardar rutinas: %s", error)


def crear_rutina(nombre: str, hora: str, comandos: list[dict[str, Any]]) -> str:
    """
    Crea una nueva rutina o reemplaza una existente.

    Args:
        nombre (str): Nombre de la rutina (ej: "mañana", "noche").
        hora (str): Hora de ejecución en formato "HH:MM" (ej: "07:00").
                    Puede ser "" si no tiene hora (solo manual).
        comandos (list): Lista de dicts con comando y parametros.

    Retorna:
        str: Mensaje de confirmación.
    """
    rutinas = cargar_rutinas()

    rutinas[nombre.lower()] = {
        "nombre": nombre.lower(),
        "hora": hora,
        "comandos": comandos,
        "activa": True
    }

    guardar_rutinas(rutinas)
    return f"Rutina '{nombre}' guardada con {len(comandos)} comandos."


def eliminar_rutina(nombre: str) -> str:
    """Elimina una rutina por nombre."""
    rutinas = cargar_rutinas()
    nombre = nombre.lower()

    if nombre not in rutinas:
        return f"No existe una rutina llamada '{nombre}'."

    del rutinas[nombre]
    guardar_rutinas(rutinas)
    return f"Rutina '{nombre}' eliminada."


def listar_rutinas() -> str:
    """Retorna un texto con todas las rutinas guardadas."""
    rutinas = cargar_rutinas()

    if not rutinas:
        return "No tienes rutinas guardadas."

    partes = []
    for nombre, datos in rutinas.items():
        n_comandos = len(datos.get("comandos", []))
        hora = datos.get("hora", "sin hora")
        estado = "activa" if datos.get("activa", True) else "pausada"
        partes.append(f"{nombre}: {hora}, {n_comandos} comandos, {estado}")

    return "Tus rutinas: " + ". ".join(partes) + "."


def obtener_rutina(nombre: str) -> dict[str, Any] | None:
    """Retorna los datos de una rutina por nombre, o None."""
    rutinas = cargar_rutinas()
    return rutinas.get(nombre.lower())


# ============================================================
# 3. EJECUCIÓN DE RUTINAS
# ============================================================

def ejecutar_rutina(
    nombre: str,
    ejecutar_comando_fn: Callable[[str, dict[str, Any]], str | None],
    hablar_fn: Callable[[str], None],
) -> str:
    """
    Ejecuta todos los comandos de una rutina en secuencia.

    Args:
        nombre (str): Nombre de la rutina.
        ejecutar_comando_fn: Función ejecutar_comando() de pc_control.
        hablar_fn: Función hablar() de Eli.

    Retorna:
        str: Mensaje resumen de la ejecución.
    """
    datos = obtener_rutina(nombre)

    if not datos:
        return f"No existe una rutina llamada '{nombre}'."

    comandos = datos.get("comandos", [])
    if not comandos:
        return f"La rutina '{nombre}' no tiene comandos."

    hablar_fn(f"Ejecutando rutina {nombre}.")

    for cmd in comandos:
        comando = cmd.get("comando", "")
        parametros = cmd.get("parametros", {})

        respuesta = ejecutar_comando_fn(comando, parametros)
        if respuesta:
            log.info("🤖 Rutina [%s]: %s", nombre, respuesta)
            hablar_fn(respuesta)

        time.sleep(1.5)  # Pausa entre comandos.

    return f"Rutina {nombre} completada."


# ============================================================
# 4. SCHEDULER — Hilo que verifica las horas
# ============================================================

class SchedulerRutinas:
    """
    Hilo en segundo plano que verifica cada minuto si alguna
    rutina programada debe ejecutarse.

    Compara la hora actual (HH:MM) con la hora de cada rutina.
    Si coincide y no se ha ejecutado hoy, la ejecuta.

    Se ejecuta como daemon: muere cuando Eli se cierra.
    """

    def __init__(
        self,
        ejecutar_comando_fn: Callable[[str, dict[str, Any]], str | None],
        hablar_fn: Callable[[str], None],
    ) -> None:
        self.ejecutar_comando_fn = ejecutar_comando_fn
        self.hablar_fn = hablar_fn
        self.corriendo: bool = False
        self.hilo: threading.Thread | None = None

        # Set de rutinas que ya se ejecutaron hoy.
        # Se limpia a medianoche (cuando el día cambia).
        # Así cada rutina se ejecuta una vez por día máximo.
        self._ejecutadas_hoy = set()
        self._dia_actual = datetime.date.today()

    def iniciar(self) -> None:
        """Arranca el scheduler en un hilo daemon."""
        self.corriendo = True
        self.hilo = threading.Thread(target=self._loop, daemon=True)
        self.hilo.start()
        log.info("⏰ Scheduler de rutinas iniciado.")

    def detener(self) -> None:
        """Detiene el scheduler."""
        self.corriendo = False

    def _loop(self) -> None:
        """Loop principal: revisa cada 30 segundos si hay rutinas pendientes."""
        while self.corriendo:
            try:
                self._verificar_rutinas()
            except Exception as error:
                log.warning("Error en scheduler: %s", error, exc_info=True)

            # Dormir 30 segundos entre verificaciones.
            # Usamos un loop corto para que detener() responda rápido.
            for _ in range(30):
                if not self.corriendo:
                    return
                time.sleep(1)

    def _verificar_rutinas(self) -> None:
        """Verifica si alguna rutina debe ejecutarse ahora."""
        ahora = datetime.datetime.now()
        hora_actual = ahora.strftime("%H:%M")
        dia_hoy = ahora.date()

        # ¿Cambió el día? Limpiar el set de ejecutadas.
        if dia_hoy != self._dia_actual:
            self._ejecutadas_hoy.clear()
            self._dia_actual = dia_hoy

        rutinas = cargar_rutinas()

        for nombre, datos in rutinas.items():
            # ¿Tiene hora programada?
            hora_rutina = datos.get("hora", "")
            if not hora_rutina:
                continue

            # ¿Está activa?
            if not datos.get("activa", True):
                continue

            # ¿Ya se ejecutó hoy?
            if nombre in self._ejecutadas_hoy:
                continue

            # ¿Coincide la hora? (comparación exacta HH:MM)
            if hora_actual == hora_rutina:
                log.info("⏰ Ejecutando rutina programada: %s", nombre)
                self._ejecutadas_hoy.add(nombre)
                ejecutar_rutina(
                    nombre,
                    self.ejecutar_comando_fn,
                    self.hablar_fn
                )


# ============================================================
# 5. CREAR RUTINAS POR VOZ (asistida por Ollama)
# ============================================================

def crear_rutina_por_voz(texto: str, pensar_fn: Callable[..., Any]) -> str:
    """
    Interpreta una instrucción de voz para crear una rutina.

    El usuario dice algo como:
        "crea rutina mañana a las 7: abre autocad y reproduce playlist trabajo"

    Enviamos esto a Ollama con un prompt especial que le pide
    extraer: nombre, hora, y lista de comandos.

    Args:
        texto (str): Lo que dijo el usuario.
        pensar_fn: No usamos pensar() aquí para no contaminar el historial.
                   Usamos una petición directa a Ollama.

    Retorna:
        str: Mensaje de confirmación o error.
    """
    import requests

    URL_OLLAMA = "http://127.0.0.1:11434/api/chat"
    MODELO = "qwen3:8b"

    prompt = [
        {
            "role": "system",
            "content": (
                "El usuario quiere crear una rutina para su asistente de voz. "
                "Analiza su mensaje y extrae:\n"
                "1. nombre: nombre corto de la rutina\n"
                "2. hora: hora de ejecución en formato HH:MM (24h), o '' si no especificó\n"
                "3. comandos: lista de comandos a ejecutar\n\n"
                "Comandos disponibles: abrir_chrome, abrir_notepad, abrir_calculadora, "
                "abrir_explorador, abrir_word, abrir_excel, abrir_powerpoint, "
                "abrir_spotify, abrir_youtube, abrir_autocad, abrir_qgis, "
                "abrir_civil3d, abrir_arcgis, subir_volumen, bajar_volumen, "
                "silenciar, volumen_especifico (porcentaje), "
                "spotify_play, spotify_pause, spotify_siguiente, spotify_anterior, "
                "spotify_buscar (busqueda), spotify_playlist (busqueda), "
                "spotify_volumen (porcentaje), modo_oscuro, "
                "abrir_carpeta_proyectos, captura_pantalla, bloquear_pantalla\n\n"
                "Responde SOLO un JSON:\n"
                '{"nombre": "mañana", "hora": "07:00", "comandos": ['
                '{"comando": "abrir_autocad", "parametros": {}}, '
                '{"comando": "spotify_playlist", "parametros": {"busqueda": "trabajo"}}'
                "]}\n\n"
                "Si no entiendes, responde: "
                '{"error": "No entendí la rutina"}'
            )
        },
        {"role": "user", "content": texto}
    ]

    try:
        respuesta = requests.post(
            URL_OLLAMA,
            json={"model": MODELO, "messages": prompt, "stream": False},
            timeout=cfg.TIMEOUT_OLLAMA_RESUMEN,
        )
        respuesta.raise_for_status()

        texto_crudo = respuesta.json()["message"]["content"].strip()

        # Extraer JSON.
        inicio = texto_crudo.find("{")
        fin = texto_crudo.rfind("}")
        if inicio == -1 or fin == -1:
            return "No entendí la rutina. Intenta de nuevo."

        datos = json.loads(texto_crudo[inicio:fin + 1])

        if "error" in datos:
            return datos["error"]

        nombre = datos.get("nombre", "").strip()
        hora = datos.get("hora", "").strip()
        comandos = datos.get("comandos", [])

        if not nombre:
            return "No entendí el nombre de la rutina."
        if not comandos:
            return "No encontré comandos en la rutina."

        # Validar que los comandos tengan la estructura correcta.
        comandos_validos = []
        for cmd in comandos:
            if isinstance(cmd, dict) and "comando" in cmd:
                if "parametros" not in cmd:
                    cmd["parametros"] = {}
                comandos_validos.append(cmd)

        if not comandos_validos:
            return "Los comandos de la rutina no son válidos."

        # Crear la rutina.
        return crear_rutina(nombre, hora, comandos_validos)

    except json.JSONDecodeError:
        return "No pude interpretar la rutina. Intenta de nuevo."
    except Exception as error:
        return f"Error al crear la rutina: {error}"


# --- Prueba directa ---
if __name__ == "__main__":
    print("=== Prueba de rutinas ===\n")

    # Test crear rutina manualmente.
    resultado = crear_rutina("test", "08:00", [
        {"comando": "abrir_chrome", "parametros": {}},
        {"comando": "buscar_google", "parametros": {"busqueda": "noticias"}}
    ])
    print(f"Crear: {resultado}")

    # Test listar.
    print(f"Listar: {listar_rutinas()}")

    # Test eliminar.
    print(f"Eliminar: {eliminar_rutina('test')}")
    print(f"Listar: {listar_rutinas()}")
