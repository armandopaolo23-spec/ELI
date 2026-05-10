# ============================================================
# memoria.py — Sistema de memoria persistente para Eli
#
# Guarda dos tipos de información en un archivo JSON:
#
# 1. PERFIL DEL USUARIO: datos que Eli aprende con el tiempo
#    (nombre, gustos, apps favoritas, etc.)
#
# 2. RESÚMENES DE SESIÓN: al cerrar Eli, Ollama genera un
#    resumen corto de lo importante. Así Eli "recuerda" sin
#    guardar miles de líneas de historial.
#
# Estructura del archivo memoria.json:
# {
#     "perfil": {
#         "nombre": "Paolo",
#         "musica": "le gusta Bad Bunny y rock clásico",
#         "apps": "usa mucho Chrome y Word",
#         "notas": ["tiene examen el viernes", "prefiere modo oscuro"]
#     },
#     "resumenes": [
#         {
#             "fecha": "2025-06-15 14:30",
#             "contenido": "El usuario pidió buscar recetas..."
#         }
#     ]
# }
# ============================================================

import json
import os
import datetime

from logger import get_logger

log = get_logger(__name__)

# Ruta del archivo de memoria. Se guarda en la misma carpeta que Eli.
# Si mueves la carpeta de Eli, la memoria se mueve con él.
RUTA_MEMORIA = os.path.join(os.path.dirname(__file__), "memoria.json")

# Máximo de resúmenes que guardamos. Los más viejos se borran.
# 20 resúmenes × ~100 palabras = ~2000 palabras, que caben bien
# en el contexto de llama3.2 sin hacerlo lento.
MAX_RESUMENES = 20


def cargar_memoria():
    """
    Lee el archivo memoria.json y retorna su contenido.

    Si el archivo no existe (primera vez que se usa Eli),
    retorna una estructura vacía.

    Retorna:
        dict: Diccionario con "perfil" y "resumenes".
    """
    if not os.path.exists(RUTA_MEMORIA):
        return _memoria_vacia()

    try:
        with open(RUTA_MEMORIA, "r", encoding="utf-8") as archivo:
            datos = json.load(archivo)

        # Verificar estructura mínima.
        if "perfil" not in datos:
            datos["perfil"] = {}
        if "resumenes" not in datos:
            datos["resumenes"] = []

        return datos

    except (json.JSONDecodeError, IOError):
        # Archivo corrupto o ilegible. Empezar de cero.
        log.warning("memoria.json corrupto. Creando memoria nueva.")
        return _memoria_vacia()


def guardar_memoria(memoria):
    """
    Escribe el diccionario de memoria al archivo JSON.

    Args:
        memoria (dict): Diccionario con "perfil" y "resumenes".
    """
    try:
        with open(RUTA_MEMORIA, "w", encoding="utf-8") as archivo:
            # indent=2 hace que el archivo sea legible si lo abres con notepad.
            # ensure_ascii=False permite caracteres como ñ, á, etc.
            json.dump(memoria, archivo, indent=2, ensure_ascii=False)
    except IOError as error:
        log.warning("No pude guardar la memoria: %s", error)


def agregar_resumen(memoria, resumen):
    """
    Agrega un resumen de sesión a la memoria.

    Si ya hay MAX_RESUMENES, elimina el más antiguo (el primero
    de la lista) para mantener el tamaño controlado.

    Args:
        memoria (dict): La memoria actual.
        resumen (str): Texto del resumen generado por Ollama.
    """
    entrada = {
        "fecha": datetime.datetime.now().strftime("%Y-%m-%d %H:%M"),
        "contenido": resumen
    }

    memoria["resumenes"].append(entrada)

    # Recortar si hay demasiados resúmenes.
    if len(memoria["resumenes"]) > MAX_RESUMENES:
        # Eliminamos los más viejos (los primeros de la lista).
        memoria["resumenes"] = memoria["resumenes"][-MAX_RESUMENES:]


def actualizar_perfil(memoria, perfil_nuevo):
    """
    Actualiza el perfil del usuario con datos nuevos.

    No reemplaza todo el perfil, sino que mezcla los datos nuevos
    con los existentes. Si una clave ya existe, la sobreescribe
    con el valor nuevo (Ollama puede corregir datos).

    Args:
        memoria (dict): La memoria actual.
        perfil_nuevo (dict): Datos nuevos del perfil.
    """
    if not isinstance(perfil_nuevo, dict):
        return

    for clave, valor in perfil_nuevo.items():
        # Si el valor es una lista, la extendemos en vez de reemplazar.
        if isinstance(valor, list) and isinstance(memoria["perfil"].get(clave), list):
            # Agregar solo elementos nuevos (evitar duplicados).
            existentes = set(memoria["perfil"][clave])
            for item in valor:
                if item not in existentes:
                    memoria["perfil"][clave].append(item)
        else:
            memoria["perfil"][clave] = valor


def memoria_a_texto(memoria):
    """
    Convierte la memoria a texto que se inyecta en el system prompt.

    Este texto le dice a Ollama qué sabe de sesiones anteriores.
    Es conciso para no llenar el contexto.

    Args:
        memoria (dict): La memoria completa.

    Retorna:
        str: Texto formateado para el prompt, o "" si no hay memoria.
    """
    partes = []

    # --- Perfil ---
    perfil = memoria.get("perfil", {})
    if perfil:
        lineas_perfil = []
        for clave, valor in perfil.items():
            if isinstance(valor, list):
                valor_texto = ", ".join(str(v) for v in valor)
            else:
                valor_texto = str(valor)
            lineas_perfil.append(f"  {clave}: {valor_texto}")

        partes.append(
            "DATOS DEL USUARIO:\n" + "\n".join(lineas_perfil)
        )

    # --- Resúmenes recientes ---
    resumenes = memoria.get("resumenes", [])
    if resumenes:
        # Solo incluimos los últimos 5 resúmenes en el prompt.
        # Los más antiguos están guardados en el archivo pero
        # no se inyectan para no llenar el contexto.
        recientes = resumenes[-5:]
        lineas_resumen = []
        for r in recientes:
            lineas_resumen.append(f"  [{r['fecha']}] {r['contenido']}")

        partes.append(
            "RESÚMENES DE SESIONES ANTERIORES:\n" + "\n".join(lineas_resumen)
        )

    if not partes:
        return ""

    return "\n\n".join(partes)


def _memoria_vacia():
    """Retorna una estructura de memoria vacía."""
    return {
        "perfil": {},
        "resumenes": []
    }
