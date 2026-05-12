# ============================================================
# main.py — Eli optimizado
#
# OPTIMIZACIÓN: Inicio paralelo.
# Antes: micrófono → memoria → modelo → saludo (secuencial, ~8 seg).
# Ahora: micrófono + modelo se precargan EN PARALELO mientras
#   la memoria se carga, reduciendo el inicio a ~4 seg.
#
# También agrega timing a cada paso para que puedas ver en
# consola cuánto tarda cada etapa y diagnosticar cuellos de botella.
# ============================================================

from __future__ import annotations

import json
import time
import threading
from typing import Any

import config as cfg
from logger import get_logger
from wake_word import esperar_wake_word
from escuchar import escuchar, calibrar_una_vez, _q
from cerebro import pensar, limpiar_historial, inicializar, generar_resumen_sesion, precarga_modelo
from hablar import hablar
from pc_control import ejecutar_comando, configurar_voz, _consultar_clima
from interfaz import InterfazEli
import piper_tts
import vad_detector
import whisper_stt
from rutinas import (
    ejecutar_saludo,
    ejecutar_rutina,
    crear_rutina_por_voz,
    listar_rutinas,
    eliminar_rutina,
    SchedulerRutinas
)

log = get_logger(__name__)

COMANDOS_DORMIR = (
    "descansa", "eli descansa", "duerme", "eli duerme",
    "modo espera", "a dormir", "eli a dormir"
)

COMANDOS_APAGAR = (
    "apagar eli", "apágate eli", "adiós eli", "cierra eli"
)

PREFIJOS_CREAR_RUTINA = (
    "crea rutina", "crear rutina", "nueva rutina",
    "crea una rutina", "crear una rutina",
    "agrega rutina", "agregar rutina"
)

PREFIJOS_EJECUTAR_RUTINA = (
    "ejecuta rutina", "ejecutar rutina", "pon rutina",
    "activa rutina", "activar rutina", "lanza rutina"
)

PREFIJOS_ELIMINAR_RUTINA = (
    "elimina rutina", "eliminar rutina", "borra rutina", "borrar rutina"
)

FRASES_LISTAR_RUTINAS = (
    "mis rutinas", "lista rutinas", "listar rutinas",
    "qué rutinas tengo", "que rutinas tengo", "muestra rutinas"
)


def _manejar_rutinas(texto: str, gui: Any) -> str | None:
    """Verifica si el texto es un comando de rutinas."""
    for prefijo in PREFIJOS_CREAR_RUTINA:
        if texto.startswith(prefijo):
            gui.cambiar_estado("pensando")
            gui.mostrar_sistema("Creando rutina...")
            return crear_rutina_por_voz(texto, pensar)

    for prefijo in PREFIJOS_EJECUTAR_RUTINA:
        if texto.startswith(prefijo):
            nombre = texto.replace(prefijo, "").strip()
            if not nombre:
                return "¿Qué rutina quieres ejecutar?"
            gui.cambiar_estado("pensando")
            gui.mostrar_sistema(f"Ejecutando rutina {nombre}...")
            return ejecutar_rutina(nombre, ejecutar_comando, hablar)

    for prefijo in PREFIJOS_ELIMINAR_RUTINA:
        if texto.startswith(prefijo):
            nombre = texto.replace(prefijo, "").strip()
            if not nombre:
                return "¿Qué rutina quieres eliminar?"
            return eliminar_rutina(nombre)

    for frase in FRASES_LISTAR_RUTINAS:
        if frase in texto:
            return listar_rutinas()

    return None


def _lanzar_tts_anticipado(texto: str) -> threading.Thread:
    """Arranca hablar(texto) en un hilo daemon y retorna el Thread.

    Lo usa cerebro.pensar para empezar a hablar la respuesta conversacional
    en cuanto sea extraíble del stream, sin esperar que cierre el JSON.
    El Thread vuelve adjunto al resultado y _procesar_resultados hace join
    en lugar de re-hablar.
    """
    hilo = threading.Thread(target=hablar, args=(texto,), daemon=True)
    hilo.start()
    return hilo


def _procesar_resultados(resultados: list[dict[str, Any]], gui: Any) -> None:
    """Ejecuta una lista de comandos/respuestas en secuencia."""
    total = len(resultados)

    for i, resultado in enumerate(resultados):
        comando = resultado.get("comando", "ninguno")
        parametros = resultado.get("parametros", {})
        hilo_anticipado = resultado.pop("_hablar_thread", None)

        if comando != "ninguno":
            respuesta = ejecutar_comando(comando, parametros)
            if respuesta:
                gui.cambiar_estado("hablando")
                gui.mostrar_eli(respuesta)
                log.info("🤖 Eli: %s", respuesta)
                hablar(respuesta)
            else:
                gui.cambiar_estado("hablando")
                aviso = "Entendí lo que quieres pero no tengo ese comando."
                gui.mostrar_eli(aviso)
                hablar(aviso)
        else:
            respuesta = resultado.get("respuesta", "No supe qué decir.")
            gui.cambiar_estado("hablando")
            gui.mostrar_eli(respuesta)
            log.info("🤖 Eli: %s", respuesta)
            if hilo_anticipado is not None:
                # Ya empezó a hablar antes de que cerrara el JSON;
                # solo esperamos a que termine para no escucharnos a nosotros.
                hilo_anticipado.join()
            else:
                hablar(respuesta)

        if i < total - 1:
            time.sleep(cfg.DELAY_ENTRE_COMANDOS)


def main() -> None:
    t_inicio_total = time.time()

    gui = InterfazEli()
    gui.iniciar()
    configurar_voz(hablar)

    # --- INICIO PARALELO ---
    # El micrófono y el modelo de Ollama se precargan en hilos
    # separados mientras cargamos la memoria en el hilo principal.
    # Esto ahorra ~3-4 segundos en el arranque.

    gui.mostrar_sistema("Iniciando sistemas en paralelo...")

    # Hilo 1: calibrar micrófono (~0.6 seg).
    hilo_mic = threading.Thread(target=calibrar_una_vez)
    hilo_mic.start()

    # Hilo 2: precargar modelo Ollama en GPU (~3-5 seg).
    hilo_modelo = threading.Thread(target=precarga_modelo)
    hilo_modelo.start()

    # Hilo 3: precargar Whisper en GPU (~3-5 seg, depende del tamaño).
    hilo_whisper = threading.Thread(target=whisper_stt.precarga)
    hilo_whisper.start()

    # Hilo 4: precargar Silero VAD (ONNX, ~200ms).
    hilo_vad = threading.Thread(target=vad_detector.precarga)
    hilo_vad.start()

    # Hilo 5: precargar Piper TTS (ONNX, ~300-500ms).
    hilo_piper = threading.Thread(target=piper_tts.precarga)
    hilo_piper.start()

    # Hilo principal: cargar memoria + construir prompt (~0.1 seg).
    inicializar()

    # Esperar a que los hilos terminen.
    hilo_mic.join()
    hilo_modelo.join()
    hilo_whisper.join()
    hilo_vad.join()
    hilo_piper.join()

    t_init = time.time() - t_inicio_total
    log.info("⚡ Inicialización completa en %.1fs", t_init)

    # --- SALUDO ---
    gui.cambiar_estado("hablando")
    gui.mostrar_sistema("Eli iniciado")
    ejecutar_saludo(hablar, pensar, _consultar_clima)
    hablar("Di Eli cuando me necesites.")

    # --- SCHEDULER ---
    scheduler = SchedulerRutinas(ejecutar_comando, hablar)
    scheduler.iniciar()

    # --- BUCLE PRINCIPAL ---
    while gui.corriendo:

        gui.cambiar_estado("espera")
        gui.mostrar_sistema("Modo espera — di 'Eli' para activar")

        detectado = esperar_wake_word()
        if not detectado:
            break

        gui.cambiar_estado("hablando")
        gui.mostrar_sistema("¡Modo activo!")
        hablar("Dime")

        time.sleep(0.5)
        while not _q.empty():
            _q.get()

        fallos_consecutivos = 0
        ultima_interaccion = time.time()
        activo = True

        while activo and gui.corriendo:

            segundos_inactivo = time.time() - ultima_interaccion
            if segundos_inactivo >= cfg.TIMEOUT_INACTIVIDAD:
                gui.cambiar_estado("hablando")
                gui.mostrar_sistema("Timeout — volviendo a espera")
                hablar("Llevo un rato sin escucharte. Estaré en espera.")
                break

            gui.cambiar_estado("escuchando")

            # --- Timing: escuchar ---
            t0 = time.time()
            texto = escuchar()
            t_escuchar = time.time() - t0

            if not texto:
                fallos_consecutivos += 1
                if fallos_consecutivos >= cfg.MAX_FALLOS_CONSECUTIVOS:
                    gui.cambiar_estado("hablando")
                    gui.mostrar_sistema(
                        f"{cfg.MAX_FALLOS_CONSECUTIVOS} fallos — volviendo a espera"
                    )
                    hablar("No te escucho. Estaré en espera si me necesitas.")
                    break
                gui.mostrar_sistema(
                    f"No entendí ({fallos_consecutivos}/{cfg.MAX_FALLOS_CONSECUTIVOS})"
                )
                continue

            fallos_consecutivos = 0
            ultima_interaccion = time.time()
            gui.mostrar_usuario(texto)
            log.info('🎤 Tú: "%s" (escucha: %.2fs)', texto, t_escuchar)

            # ¿Dormir?
            if texto.startswith(COMANDOS_DORMIR):
                gui.cambiar_estado("hablando")
                gui.mostrar_eli("Entendido, estaré en espera.")
                hablar("Entendido, estaré en espera.")
                break

            # ¿Apagar?
            if any(texto.startswith(cmd) for cmd in COMANDOS_APAGAR):
                gui.cambiar_estado("hablando")
                gui.mostrar_eli("Hasta pronto. Apagando sistemas.")
                hablar("Hasta pronto. Apagando sistemas.")
                activo = False
                continue

            # ¿Rutinas?
            respuesta_rutina = _manejar_rutinas(texto, gui)
            if respuesta_rutina is not None:
                gui.cambiar_estado("hablando")
                gui.mostrar_eli(respuesta_rutina)
                log.info("🤖 Eli: %s", respuesta_rutina)
                hablar(respuesta_rutina)
                continue

            # --- Timing: pensar ---
            gui.cambiar_estado("pensando")
            t0 = time.time()
            resultados = pensar(texto, hablar_anticipado=_lanzar_tts_anticipado)
            t_pensar = time.time() - t0

            log.debug(
                "[JSON] %s",
                json.dumps(
                    [{k: v for k, v in r.items() if not k.startswith("_")}
                     for r in resultados],
                    ensure_ascii=False,
                ),
            )
            log.debug("⏱️ pensar: %.2fs", t_pensar)

            if len(resultados) > 1:
                log.debug("📋 %d comandos en secuencia", len(resultados))

            # --- Timing: hablar ---
            t0 = time.time()
            _procesar_resultados(resultados, gui)
            t_hablar = time.time() - t0

            log.debug(
                "⏱️ total turno: escuchar %.2fs + pensar %.2fs + hablar %.2fs = %.2fs",
                t_escuchar, t_pensar, t_hablar,
                t_escuchar + t_pensar + t_hablar,
            )

        if not activo:
            break

    # --- Limpieza ---
    scheduler.detener()
    log.info("🧠 Guardando memoria de sesión...")
    gui.mostrar_sistema("Guardando memoria...")
    generar_resumen_sesion()
    log.info("🧠 Memoria guardada.")
    gui.detener()


if __name__ == "__main__":
    main()
