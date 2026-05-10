#!/usr/bin/env python3
"""Diagnóstico de qué partes de Eli funcionan en este sistema.

Pensado para correrlo en tu Ubuntu real (donde Eli vive):

    python3 validar_ubuntu.py

NO ejecuta acciones destructivas (no bloquea pantalla, no apaga, no
cambia tema, no envía teclas, no genera audio). Solo verifica que las
herramientas necesarias estén disponibles e imprime un reporte
PASS / WARN / FAIL por cada cosa que Eli necesitaría.

Secciones del reporte:

1. Sistema base       — OS, Python, locale, desktop env, sesión.
2. Carpetas usuario   — DESKTOP / DOCUMENTS / etc. resueltas por os_compat.
3. Lanzadores apps    — busca binarios en PATH para cada app lógica.
4. Acciones SO        — loginctl/gsettings/shutdown/xdg-open según corresponda.
5. Nodos Ollama       — ping /api/tags a cada nodo configurado.
6. Deps Python        — importabilidad de paquetes críticos.
7. Audio              — sounddevice query (entradas/salidas).

Salida: tabla legible + exit code != 0 si hay fallas críticas
(carpeta proyectos faltante NO cuenta como crítica; ollama
inalcanzable y sin micrófono SÍ).
"""

from __future__ import annotations

import importlib
import locale
import os
import platform
import shutil
import sys
from pathlib import Path

# Anclar el proyecto al sys.path por si se invoca desde otra carpeta.
RAIZ = Path(__file__).resolve().parent
if str(RAIZ) not in sys.path:
    sys.path.insert(0, str(RAIZ))


# --- Símbolos y formato ---

SI = "\033[32m✅\033[0m"  # verde
WARN = "\033[33m⚠️ \033[0m"  # amarillo
NO = "\033[31m❌\033[0m"  # rojo
INFO = "\033[36mℹ️ \033[0m"  # cyan

ANCHO = 76

_fallos_criticos = 0


def header(titulo: str) -> None:
    print()
    print("─" * ANCHO)
    print(f" {titulo}")
    print("─" * ANCHO)


def linea(simbolo: str, descripcion: str, detalle: str = "") -> None:
    if detalle:
        print(f"  {simbolo}  {descripcion:24}  {detalle}")
    else:
        print(f"  {simbolo}  {descripcion}")


def fallo_critico(descripcion: str, detalle: str = "") -> None:
    global _fallos_criticos
    _fallos_criticos += 1
    linea(NO, descripcion, detalle)


# ============================================================
# 1. Sistema base
# ============================================================

def chequeo_sistema() -> None:
    header("1. Sistema base")
    linea(INFO, "OS", f"{platform.system()} {platform.release()}")
    linea(INFO, "Python", platform.python_version())
    try:
        loc = locale.getlocale()[0] or "(no detectado)"
    except Exception:
        loc = "(no detectado)"
    linea(INFO, "Locale", loc)
    linea(
        INFO, "Desktop Env",
        os.environ.get("XDG_CURRENT_DESKTOP")
        or os.environ.get("DESKTOP_SESSION")
        or "(no detectado)",
    )
    linea(INFO, "Sesión", os.environ.get("XDG_SESSION_TYPE") or "(no detectado)")


# ============================================================
# 2. Carpetas del usuario
# ============================================================

def chequeo_carpetas(os_compat) -> None:
    header("2. Carpetas del usuario (resueltas por os_compat)")
    carpetas = [
        ("HOME", os_compat.HOME),
        ("DESKTOP", os_compat.DESKTOP),
        ("DOCUMENTS", os_compat.DOCUMENTS),
        ("DOWNLOADS", os_compat.DOWNLOADS),
        ("PICTURES", os_compat.PICTURES),
        ("VIDEOS", os_compat.VIDEOS),
        ("MUSIC", os_compat.MUSIC),
        ("CARPETA_PROYECTOS", os_compat.CARPETA_PROYECTOS),
    ]
    for nombre, ruta in carpetas:
        existe = Path(ruta).exists()
        simbolo = SI if existe else WARN
        detalle = str(ruta) + ("" if existe else "  (no existe)")
        linea(simbolo, nombre, detalle)


# ============================================================
# 3. Lanzadores de apps
# ============================================================

def chequeo_apps(os_compat) -> None:
    header("3. Lanzadores de apps (binario en PATH)")
    if not os_compat.IS_LINUX:
        linea(INFO, "Skip", "no es Linux; los lanzadores de Windows no se prueban aquí")
        return

    for nombre, spec in os_compat._APPS.items():
        encontrado = None
        for variante in spec["linux"]:
            if shutil.which(variante[0]):
                encontrado = " ".join(variante)
                break
        if encontrado:
            linea(SI, nombre, encontrado)
        else:
            candidatos = ", ".join(v[0] for v in spec["linux"])
            linea(WARN, nombre, f"no instalado (probé: {candidatos})")


# ============================================================
# 4. Acciones del sistema
# ============================================================

def chequeo_acciones(os_compat) -> None:
    header("4. Acciones del sistema (herramientas disponibles)")
    if not os_compat.IS_LINUX:
        linea(INFO, "Skip", "no es Linux")
        return

    acciones: list[tuple[str, list[str]]] = [
        ("bloquear_pantalla", [
            "loginctl", "xdg-screensaver",
            "gnome-screensaver-command", "dm-tool",
        ]),
        ("apagar_pc/cancelar", ["shutdown"]),
        ("modo_oscuro_toggle", ["gsettings"]),
        ("abrir_path", ["xdg-open"]),
        ("xdg-user-dir locale", ["xdg-user-dir"]),
    ]

    for accion, candidatos in acciones:
        disponibles = [b for b in candidatos if shutil.which(b)]
        if disponibles:
            linea(SI, accion, ", ".join(disponibles))
        elif accion == "modo_oscuro_toggle":
            # GNOME-only; en KDE u otros DEs no aplica.
            linea(WARN, accion, "gsettings ausente (no-GNOME)")
        else:
            fallo_critico(accion, f"falta cualquiera de: {', '.join(candidatos)}")

    # Trash spec del FreeDesktop (lo crea el primer borrado, no es fallo).
    trash = os_compat.HOME / ".local" / "share" / "Trash"
    if trash.exists():
        linea(SI, "vaciar_papelera", f"{trash} OK")
    else:
        linea(INFO, "vaciar_papelera", f"{trash} aún no existe (se crea al borrar)")


# ============================================================
# 5. Nodos Ollama
# ============================================================

def chequeo_ollama() -> None:
    header("5. Nodos Ollama")
    try:
        import requests
    except ImportError:
        fallo_critico("requests", "no instalado")
        return

    try:
        from cerebro import NODOS
        import config as cfg
    except Exception as error:
        fallo_critico("import cerebro", str(error))
        return

    timeout = getattr(cfg, "TIMEOUT_OLLAMA_PING", 2)
    for nodo in NODOS:
        try:
            r = requests.get(nodo["url_tags"], timeout=timeout)
            if r.status_code == 200:
                # Intentar listar modelos disponibles.
                try:
                    modelos = [m["name"] for m in r.json().get("models", [])]
                    tiene_modelo = nodo["modelo"] in modelos
                    detalle = f"OK — {nodo['modelo']} {'instalado' if tiene_modelo else 'NO instalado'}"
                    simbolo = SI if tiene_modelo else WARN
                except Exception:
                    detalle = f"OK ({nodo['modelo']})"
                    simbolo = SI
                linea(simbolo, nodo["nombre"], detalle)
            else:
                linea(WARN, nodo["nombre"], f"HTTP {r.status_code}")
        except requests.RequestException as e:
            mensaje = _resumir_error_red(e, timeout)
            if nodo["nombre"] == "PCN":
                _registrar_fallo()
                linea(NO, nodo["nombre"], mensaje)
            else:
                linea(WARN, nodo["nombre"], mensaje)


def _resumir_error_red(e: Exception, timeout: int) -> str:
    """Acorta los traceback gigantes de requests a una línea útil."""
    nombre = e.__class__.__name__
    if "Timeout" in nombre:
        return f"timeout ({timeout}s)"
    if "ConnectionError" in nombre:
        return "no responde (¿Ollama corriendo?)"
    return nombre


def _registrar_fallo() -> None:
    global _fallos_criticos
    _fallos_criticos += 1


# ============================================================
# 6. Deps Python
# ============================================================

def chequeo_deps() -> None:
    header("6. Dependencias Python")
    criticas = ["numpy", "scipy", "sounddevice", "soundfile", "edge_tts",
                "speech_recognition", "requests"]
    opcionales = ["pyautogui", "psutil", "spotipy", "googleapiclient",
                  "selenium", "tkinter"]

    for d in criticas:
        try:
            importlib.import_module(d)
            linea(SI, d, "instalado")
        except ImportError:
            fallo_critico(d, "no instalado (crítico)")

    for d in opcionales:
        try:
            importlib.import_module(d)
            linea(SI, d, "instalado")
        except ImportError:
            linea(WARN, d, "no instalado (opcional)")


# ============================================================
# 7. Audio
# ============================================================

def chequeo_audio() -> None:
    header("7. Audio (sin generar sonido)")
    try:
        import sounddevice
    except ImportError:
        fallo_critico("sounddevice", "no instalado")
        return

    try:
        dispositivos = sounddevice.query_devices()
    except Exception as error:
        fallo_critico("query_devices", str(error))
        return

    n_in = sum(1 for d in dispositivos if d["max_input_channels"] > 0)
    n_out = sum(1 for d in dispositivos if d["max_output_channels"] > 0)

    if n_in:
        linea(SI, "Entradas (mic)", f"{n_in} dispositivos")
    else:
        fallo_critico("Entradas (mic)", "0 dispositivos — Eli no podrá escuchar")

    if n_out:
        linea(SI, "Salidas (speaker)", f"{n_out} dispositivos")
    else:
        fallo_critico("Salidas (speaker)", "0 dispositivos — Eli no podrá hablar")

    # Default device, si lo hay.
    try:
        default = sounddevice.default.device
        linea(INFO, "Default", f"input={default[0]} output={default[1]}")
    except Exception:
        pass


# ============================================================
# Main
# ============================================================

def main() -> int:
    print("Validador de Eli en Ubuntu")
    print("Diagnóstico no destructivo. No abre apps, no apaga, no hace ruido.")

    chequeo_sistema()

    # os_compat es necesario para las secciones 2-4. Si falla aquí,
    # cortamos para no enmascarar el problema.
    try:
        import os_compat
    except Exception as error:
        fallo_critico("import os_compat", str(error))
        return _resumen()

    chequeo_carpetas(os_compat)
    chequeo_apps(os_compat)
    chequeo_acciones(os_compat)
    chequeo_ollama()
    chequeo_deps()
    chequeo_audio()

    return _resumen()


def _resumen() -> int:
    print()
    print("─" * ANCHO)
    if _fallos_criticos == 0:
        print(f"  {SI}  Sin fallos críticos. Eli debería arrancar.")
        codigo = 0
    else:
        print(f"  {NO}  {_fallos_criticos} fallo(s) crítico(s). Revisa los marcados con {NO}.")
        codigo = 1
    print("─" * ANCHO)
    print(
        "  Los ⚠️ son apps/herramientas opcionales — solo afectan comandos\n"
        "  específicos (ej: sin gsettings no funciona modo_oscuro, pero el\n"
        "  resto de Eli sigue corriendo)."
    )
    return codigo


if __name__ == "__main__":
    sys.exit(main())
