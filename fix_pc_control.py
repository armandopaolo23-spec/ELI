#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# Leer el archivo
with open('pc_control.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Cambio 1: Reemplazar _volumen_especifico
old_volumen = 'def _volumen_especifico(texto):'
if old_volumen in content:
    # Encontrar desde 'def _volumen_especifico' hasta el siguiente 'return'
    start = content.find(old_volumen)
    end = content.find('\n\n# ============================================================\n# SPOTIFY', start)
    
    old_section = content[start:end]
    
    new_volumen = '''def _volumen_especifico(params):
    porcentaje = params.get("porcentaje", 50)
    try:
        porcentaje = int(porcentaje)
    except:
        porcentaje = 50
    porcentaje = max(0, min(100, porcentaje))
    for _ in range(50):
        pyautogui.press("volumedown")
    for _ in range(porcentaje // 2):
        pyautogui.press("volumeup")
    return f"Volumen ajustado al {porcentaje} por ciento."'''
    
    content = content.replace(old_section, new_volumen)
    print("[✓] Función _volumen_especifico actualizada")

# Cambio 2: Agregar _abrir_spotify
if 'def _abrir_spotify' not in content:
    old_powerpoint = '''def _abrir_powerpoint(texto):
    os.system("start powerpnt")
    return "Abriendo PowerPoint."'''
    
    new_powerpoint = '''def _abrir_powerpoint(texto):
    os.system("start powerpnt")
    return "Abriendo PowerPoint."


def _abrir_spotify(params):
    os.system("start spotify")
    return "Abriendo Spotify."'''
    
    content = content.replace(old_powerpoint, new_powerpoint)
    print("[✓] Función _abrir_spotify agregada")

# Cambio 3: Agregar a DISPATCH
if '"abrir_spotify"' not in content:
    old_dispatch = '''    "abrir_powerpoint":      _abrir_powerpoint,
    "abrir_youtube":         _abrir_youtube,'''
    
    new_dispatch = '''    "abrir_powerpoint":      _abrir_powerpoint,
    "abrir_spotify":         _abrir_spotify,
    "abrir_youtube":         _abrir_youtube,'''
    
    content = content.replace(old_dispatch, new_dispatch)
    print("[✓] DISPATCH actualizado con abrir_spotify")

# Guardar
with open('pc_control.py', 'w', encoding='utf-8') as f:
    f.write(content)

print("\n[✓] Archivo pc_control.py actualizado exitosamente")
