"""Compat de SO para Eli.

Centraliza detección de plataforma, rutas del usuario, y wrappers de
acciones que tienen implementación distinta entre Linux/Windows/Mac.

Diseño:
- Linux primario, Windows como fallback (preserva el comportamiento
  histórico para quienes aún corren Eli en Windows).
- Cada acción retorna True/False (o un valor) para que el caller pueda
  dar un mensaje útil cuando la operación no se pudo completar.
- Los lanzamientos de apps se intentan en orden de probabilidad:
  primero el binario más común, luego flatpak/snap si aplica.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

from logger import get_logger

log = get_logger(__name__)


IS_LINUX = sys.platform.startswith("linux")
IS_WINDOWS = sys.platform.startswith("win")
IS_MAC = sys.platform == "darwin"

HOME = Path.home()


# ============================================================
# CARPETAS DEL USUARIO
# ============================================================

def _xdg_user_dir(nombre: str) -> Path:
    """Resuelve carpeta XDG (Documents, Downloads, etc.) en Linux.

    Usa xdg-user-dir si está disponible (respeta locale del SO, así
    "Escritorio" en español se resuelve a $HOME/Escritorio en vez de
    $HOME/Desktop).
    """
    try:
        salida = subprocess.run(
            ["xdg-user-dir", nombre],
            capture_output=True, text=True, timeout=2,
        )
        ruta = salida.stdout.strip()
        if ruta:
            return Path(ruta)
    except (FileNotFoundError, subprocess.SubprocessError, OSError):
        pass

    # Fallback: probar nombre en español primero (Ubuntu en español),
    # luego inglés.
    fallbacks = {
        "DESKTOP":   ("Escritorio", "Desktop"),
        "DOCUMENTS": ("Documentos", "Documents"),
        "DOWNLOAD":  ("Descargas", "Downloads"),
        "PICTURES":  ("Imágenes", "Pictures"),
        "VIDEOS":    ("Vídeos", "Videos"),
        "MUSIC":     ("Música", "Music"),
    }
    for candidato in fallbacks.get(nombre, (nombre.title(),)):
        ruta = HOME / candidato
        if ruta.exists():
            return ruta
    # Último recurso: el primero del fallback aunque no exista.
    return HOME / fallbacks.get(nombre, (nombre.title(),))[0]


if IS_LINUX:
    DESKTOP   = _xdg_user_dir("DESKTOP")
    DOCUMENTS = _xdg_user_dir("DOCUMENTS")
    DOWNLOADS = _xdg_user_dir("DOWNLOAD")
    PICTURES  = _xdg_user_dir("PICTURES")
    VIDEOS    = _xdg_user_dir("VIDEOS")
    MUSIC     = _xdg_user_dir("MUSIC")
    CARPETA_PROYECTOS = DESKTOP / "Carpeta proyectos"
else:
    DESKTOP   = HOME / "Desktop"
    DOCUMENTS = HOME / "Documents"
    DOWNLOADS = HOME / "Downloads"
    PICTURES  = HOME / "Pictures"
    VIDEOS    = HOME / "Videos"
    MUSIC     = HOME / "Music"
    CARPETA_PROYECTOS = Path(r"C:\Users\Lenovo\OneDrive\Desktop\Carpeta proyectos")


# ============================================================
# ABRIR ARCHIVO/CARPETA EN APP DEFAULT
# ============================================================

def abrir_path(ruta: str | Path) -> bool:
    """Abre un archivo o carpeta con la app por default del SO.

    Retorna True si lanzó algo, False si no pudo.
    """
    ruta_str = str(ruta)
    if not os.path.exists(ruta_str):
        return False
    try:
        if IS_WINDOWS:
            os.startfile(ruta_str)  # type: ignore[attr-defined]
            return True
        if IS_LINUX:
            subprocess.Popen(["xdg-open", ruta_str])
            return True
        if IS_MAC:
            subprocess.Popen(["open", ruta_str])
            return True
    except (OSError, FileNotFoundError) as error:
        log.warning("abrir_path('%s') falló: %s", ruta_str, error)
    return False


# ============================================================
# LANZAR APLICACIONES POR NOMBRE
# ============================================================
#
# Cada app tiene comandos por SO. En Linux probamos el primero que
# esté en PATH; en Windows usamos `start <alias>` que el shell
# resuelve contra el registry y los .lnk del Start Menu.

_APPS = {
    "chrome": {
        "windows": ["start", "chrome"],
        "linux":   [["google-chrome"], ["chromium-browser"], ["chromium"], ["flatpak", "run", "com.google.Chrome"]],
    },
    "terminal": {
        "windows": ["start", "cmd"],
        "linux":   [["gnome-terminal"], ["xterm"], ["xfce4-terminal"], ["konsole"]],
    },
    "vscode": {
        "windows": ["start", "code"],
        "linux":   [["code"], ["code-insiders"], ["codium"]],
    },
    "notepad": {
        "windows": ["notepad"],
        "linux":   [["gedit"], ["gnome-text-editor"], ["kate"], ["xdg-open", "/dev/null"]],
    },
    "calculadora": {
        "windows": ["calc"],
        "linux":   [["gnome-calculator"], ["kcalc"], ["galculator"]],
    },
    "explorador": {
        "windows": ["explorer"],
        "linux":   [["xdg-open", str(HOME)]],
    },
    "configuracion": {
        "windows": ["start", "ms-settings:"],
        "linux":   [["gnome-control-center"], ["systemsettings5"], ["xdg-open", "settings:"]],
    },
    "word": {
        "windows": ["start", "winword"],
        "linux":   [["libreoffice", "--writer"], ["soffice", "--writer"]],
    },
    "excel": {
        "windows": ["start", "excel"],
        "linux":   [["libreoffice", "--calc"], ["soffice", "--calc"]],
    },
    "powerpoint": {
        "windows": ["start", "powerpnt"],
        "linux":   [["libreoffice", "--impress"], ["soffice", "--impress"]],
    },
    "spotify": {
        "windows": [r'start "" "C:\Users\Lenovo\OneDrive\Desktop\Spotify.lnk"'],
        "linux":   [["spotify"], ["flatpak", "run", "com.spotify.Client"], ["snap", "run", "spotify"]],
    },
}


def abrir_app(nombre: str) -> bool:
    """Lanza una app por nombre lógico (chrome, notepad, etc.).

    Retorna True si encontró un lanzador y arrancó el proceso.
    """
    spec = _APPS.get(nombre)
    if spec is None:
        log.warning("abrir_app: nombre desconocido '%s'", nombre)
        return False

    if IS_WINDOWS:
        cmd = spec["windows"]
        try:
            # Si es lista, usar shell=False para argumentos seguros;
            # si es string, shell=True para que `start` funcione.
            if isinstance(cmd, list):
                if cmd and cmd[0] == "start":
                    os.system(" ".join(cmd))
                else:
                    subprocess.Popen(cmd)
            else:
                os.system(cmd)
            return True
        except OSError as error:
            log.warning("abrir_app('%s') falló en Windows: %s", nombre, error)
            return False

    if IS_LINUX:
        for variante in spec["linux"]:
            binario = variante[0]
            if not shutil.which(binario):
                continue
            try:
                subprocess.Popen(variante)
                return True
            except OSError as error:
                log.warning("abrir_app('%s') falló con %s: %s", nombre, binario, error)
                continue
        log.info("abrir_app('%s'): ninguna variante disponible en PATH", nombre)
        return False

    return False


# ============================================================
# ACCIONES DEL SISTEMA
# ============================================================

def bloquear_pantalla() -> bool:
    """Bloquea la pantalla. Retorna True si lanzó la acción."""
    if IS_WINDOWS:
        try:
            subprocess.Popen("rundll32.exe user32.dll,LockWorkStation", shell=True)
            return True
        except OSError:
            return False
    if IS_LINUX:
        # Probar varias opciones (loginctl es el más universal en
        # systemd; xdg-screensaver y los gnome/kde son fallbacks).
        for cmd in (
            ["loginctl", "lock-session"],
            ["xdg-screensaver", "lock"],
            ["gnome-screensaver-command", "--lock"],
            ["dm-tool", "lock"],
        ):
            if not shutil.which(cmd[0]):
                continue
            try:
                subprocess.Popen(cmd)
                return True
            except OSError:
                continue
        return False
    if IS_MAC:
        try:
            subprocess.Popen([
                "osascript", "-e",
                'tell application "System Events" to keystroke "q" using {control down, command down}',
            ])
            return True
        except OSError:
            return False
    return False


def apagar_pc(segundos: int = 60) -> bool:
    """Programa apagado. Retorna True si lanzó la acción."""
    if IS_WINDOWS:
        try:
            subprocess.Popen(f"shutdown /s /t {segundos}", shell=True)
            return True
        except OSError:
            return False
    if IS_LINUX:
        # `shutdown -h +N` toma minutos. Redondeamos hacia arriba para
        # respetar el tiempo solicitado.
        minutos = max(1, (segundos + 59) // 60)
        try:
            subprocess.Popen(["shutdown", "-h", f"+{minutos}"])
            return True
        except (FileNotFoundError, OSError):
            return False
    if IS_MAC:
        minutos = max(1, (segundos + 59) // 60)
        try:
            subprocess.Popen(["sudo", "shutdown", "-h", f"+{minutos}"])
            return True
        except OSError:
            return False
    return False


def cancelar_apagado() -> bool:
    """Cancela un apagado programado. Retorna True si lo cancela."""
    if IS_WINDOWS:
        try:
            subprocess.Popen("shutdown /a", shell=True)
            return True
        except OSError:
            return False
    if IS_LINUX:
        try:
            subprocess.Popen(["shutdown", "-c"])
            return True
        except (FileNotFoundError, OSError):
            return False
    return False  # macOS no tiene cancel directo seguro


def vaciar_papelera() -> bool:
    """Vacía la papelera del usuario. Retorna True si la operación
    completó (también True si la papelera ya estaba vacía)."""
    if IS_WINDOWS:
        try:
            subprocess.Popen(
                'powershell -Command "Clear-RecycleBin -Force -ErrorAction SilentlyContinue"',
                shell=True,
            )
            return True
        except OSError:
            return False
    if IS_LINUX:
        # Trash spec del FreeDesktop: ~/.local/share/Trash/{files,info}
        trash = HOME / ".local" / "share" / "Trash"
        if not trash.exists():
            return True
        try:
            for sub in ("files", "info"):
                directorio = trash / sub
                if not directorio.exists():
                    continue
                for entrada in directorio.iterdir():
                    if entrada.is_dir() and not entrada.is_symlink():
                        shutil.rmtree(entrada, ignore_errors=True)
                    else:
                        try:
                            entrada.unlink()
                        except OSError:
                            pass
            return True
        except OSError as error:
            log.warning("vaciar_papelera falló: %s", error)
            return False
    return False


def controlar_ventana_activa(accion: str) -> bool:
    """Controla la ventana activa usando wmctrl.

    accion: 'minimizar' | 'maximizar' | 'cerrar'
    Retorna True si el comando se lanzó, False si wmctrl no está disponible.
    """
    if not IS_LINUX:
        return False
    if not shutil.which("wmctrl"):
        log.warning("controlar_ventana_activa: wmctrl no encontrado en PATH")
        return False
    cmds = {
        "minimizar": ["wmctrl", "-r", ":ACTIVE:", "-b", "add,hidden"],
        "maximizar": ["wmctrl", "-r", ":ACTIVE:", "-b", "add,maximized_vert,maximized_horz"],
        "cerrar":    ["wmctrl", "-c", ":ACTIVE:"],
    }
    cmd = cmds.get(accion)
    if cmd is None:
        log.warning("controlar_ventana_activa: acción desconocida '%s'", accion)
        return False
    try:
        subprocess.Popen(cmd)
        return True
    except (FileNotFoundError, OSError) as error:
        log.warning("controlar_ventana_activa('%s') falló: %s", accion, error)
        return False


def modo_oscuro_toggle() -> str | None:
    """Alterna modo oscuro/claro. Retorna 'oscuro', 'claro', o None
    si no se pudo cambiar."""
    if IS_WINDOWS:
        ruta_reg = r"HKCU\SOFTWARE\Microsoft\Windows\CurrentVersion\Themes\Personalize"
        try:
            resultado = subprocess.run(
                f'reg query "{ruta_reg}" /v AppsUseLightTheme',
                shell=True, capture_output=True, text=True,
            )
            es_oscuro = "0x0" in resultado.stdout
            nuevo = "1" if es_oscuro else "0"
            for clave in ("AppsUseLightTheme", "SystemUsesLightTheme"):
                subprocess.run(
                    f'reg add "{ruta_reg}" /v {clave} /t REG_DWORD /d {nuevo} /f',
                    shell=True, capture_output=True,
                )
            return "claro" if es_oscuro else "oscuro"
        except OSError:
            return None
    if IS_LINUX:
        # GNOME 42+ usa color-scheme; antes era gtk-theme.
        if not shutil.which("gsettings"):
            return None
        try:
            actual = subprocess.run(
                ["gsettings", "get", "org.gnome.desktop.interface", "color-scheme"],
                capture_output=True, text=True, timeout=2,
            ).stdout.strip().strip("'")
            if actual == "prefer-dark":
                nuevo, etiqueta = "default", "claro"
            else:
                nuevo, etiqueta = "prefer-dark", "oscuro"
            subprocess.run(
                ["gsettings", "set", "org.gnome.desktop.interface", "color-scheme", nuevo],
                check=False, timeout=2,
            )
            return etiqueta
        except (FileNotFoundError, subprocess.SubprocessError, OSError):
            return None
    return None
