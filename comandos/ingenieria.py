"""Apps de ingeniería (AutoCAD/Civil 3D/QGIS/ArcGIS) + manejo de archivos.

Estrategia para encontrar ejecutables: primero ``shutil.which()`` que
busca en el PATH; si no aparece, se prueban rutas conocidas con globs.
AutoCAD/Civil 3D/ArcGIS Pro son productos solo Windows. En Linux esos
globs no matchean y la función devuelve "no encontré". QGIS sí corre
en Linux y se busca en /usr/bin y /usr/local/bin además de las rutas
Windows.
"""

from __future__ import annotations

import glob
import os
import shutil
import subprocess
from typing import Any

import os_compat
from logger import get_logger

log = get_logger(__name__)


# ============================================================
# RUTAS CONOCIDAS DE LOS EJECUTABLES
# ============================================================

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

# Carpeta de proyectos: resuelta por SO desde os_compat.
CARPETA_PROYECTOS = str(os_compat.CARPETA_PROYECTOS)


def _buscar_ejecutable(
    nombre_comando: str, rutas_conocidas: list[str]
) -> str | None:
    """Busca un ejecutable: primero en PATH, luego en rutas conocidas."""
    ruta = shutil.which(nombre_comando)
    if ruta:
        return ruta

    for patron in rutas_conocidas:
        resultados = glob.glob(patron)
        if resultados:
            resultados.sort()
            return resultados[-1]

    return None


# ============================================================
# PROGRAMAS DE INGENIERÍA
# ============================================================

def _abrir_autocad(params: dict[str, Any]) -> str:
    ruta = _buscar_ejecutable("acad", RUTAS_AUTOCAD)
    if ruta:
        subprocess.Popen([ruta])
        return "Abriendo AutoCAD."
    return "No encontré AutoCAD instalado. Verifica la instalación."


def _abrir_civil3d(params: dict[str, Any]) -> str:
    """Civil 3D comparte el ejecutable de AutoCAD; intenta primero el
    acceso directo del menú inicio (Windows), luego AutoCAD."""
    resultado = os.system('start "" "Civil 3D"')
    if resultado == 0:
        return "Abriendo Civil 3D."

    ruta = _buscar_ejecutable("acad", RUTAS_CIVIL3D)
    if ruta:
        subprocess.Popen([ruta])
        return "Abriendo AutoCAD con Civil 3D."
    return "No encontré Civil 3D instalado. Verifica la instalación."


def _abrir_qgis(params: dict[str, Any]) -> str:
    ruta = _buscar_ejecutable("qgis", RUTAS_QGIS)
    if ruta:
        subprocess.Popen([ruta])
        return "Abriendo QGIS."

    resultado = os.system('start "" "QGIS"')
    if resultado == 0:
        return "Abriendo QGIS."
    return "No encontré QGIS instalado. Verifica la instalación."


def _abrir_arcgis(params: dict[str, Any]) -> str:
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

def _abrir_carpeta_proyectos(params: dict[str, Any]) -> str:
    """Abre la carpeta de proyectos. La crea si no existía."""
    carpeta = params.get("carpeta", CARPETA_PROYECTOS)

    if os.path.exists(carpeta):
        if os_compat.abrir_path(carpeta):
            return "Abriendo carpeta de proyectos."
        return "No pude abrir la carpeta de proyectos."

    try:
        os.makedirs(carpeta, exist_ok=True)
        if os_compat.abrir_path(carpeta):
            return "Creé y abrí la carpeta de proyectos."
        return "Creé la carpeta pero no pude abrirla."
    except OSError:
        return "No pude abrir la carpeta de proyectos."


def _abrir_en_carpeta(params: dict[str, Any]) -> str:
    """Abre el explorador en una carpeta del usuario.

    Las rutas vienen resueltas por locale desde ``os_compat``.
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

    if os.path.exists(destino):
        if os_compat.abrir_path(destino):
            return f"Abriendo {destino}."

    return f"No encontré la carpeta '{destino}'."


def _buscar_archivos(params: dict[str, Any]) -> str:
    """Busca archivos por extensión en la carpeta de proyectos."""
    extension = params.get("extension", "").strip().lstrip(".")

    if not extension:
        return "¿Qué tipo de archivos quieres buscar? Dime la extensión, por ejemplo DWG o SHP."

    patron = os.path.join(CARPETA_PROYECTOS, "**", f"*.{extension}")
    archivos = glob.glob(patron, recursive=True)

    if not archivos:
        return f"No encontré archivos .{extension} en la carpeta de proyectos."

    total = len(archivos)
    muestra = archivos[:5]
    nombres = [os.path.basename(a) for a in muestra]
    lista = ", ".join(nombres)

    if total <= 5:
        return f"Encontré {total} archivos .{extension}: {lista}."
    return f"Encontré {total} archivos .{extension}. Los primeros: {lista}."


def _crear_carpeta(params: dict[str, Any]) -> str:
    """Crea una carpeta dentro de la carpeta de proyectos."""
    nombre = params.get("nombre", "").strip()

    if not nombre:
        return "¿Cómo quieres que se llame la carpeta?"

    # Limpiar caracteres no válidos para nombres de carpeta en Windows.
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


DISPATCH: dict[str, Any] = {
    "abrir_autocad":           _abrir_autocad,
    "abrir_civil3d":           _abrir_civil3d,
    "abrir_qgis":              _abrir_qgis,
    "abrir_arcgis":            _abrir_arcgis,
    "abrir_carpeta_proyectos": _abrir_carpeta_proyectos,
    "abrir_en_carpeta":        _abrir_en_carpeta,
    "buscar_archivos":         _buscar_archivos,
    "crear_carpeta":           _crear_carpeta,
}
