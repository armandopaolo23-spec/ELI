from blackboard_api import BlackboardAPI
import webbrowser
import subprocess


def listar_mis_cursos():
    """Lista los cursos del usuario"""
    api = BlackboardAPI()
    cursos = api.listar_cursos()
    
    if not cursos:
        return "No se encontraron cursos"
    
    texto = f"Tienes {len(cursos)} cursos:\n"
    for i, curso in enumerate(cursos, 1):
        texto += f"{i}. {curso['nombre']}\n"
    
    return texto


def abrir_curso(nombre_curso):
    """Abre un curso en el navegador"""
    api = BlackboardAPI()
    cursos = api.listar_cursos()
    
    # Buscar curso por nombre (case insensitive, parcial)
    nombre_lower = nombre_curso.lower()
    for curso in cursos:
        if nombre_lower in curso['nombre'].lower():
            subprocess.run(['chromium-browser', curso['url']])
            return f"Abriendo {curso['nombre']}"
    
    return f"No se encontró el curso '{nombre_curso}'"


# Mapa de funciones para pc_control.py
BLACKBOARD_COMMANDS = {
    "listar_cursos": listar_mis_cursos,
    "abrir_curso": abrir_curso
}
