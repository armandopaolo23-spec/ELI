import re

# Leer el archivo
with open('pc_control.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Reemplazar _volumen_especifico
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

# Usar regex para reemplazar la función
content = re.sub(
    r'def _volumen_especifico\(texto\):.*?return f"Volumen ajustado al \{porcentaje\} por ciento\."',
    new_volumen,
    content,
    flags=re.DOTALL
)

# Agregar _abrir_spotify después de _abrir_powerpoint
new_spotify = '''def _abrir_powerpoint(texto):
    os.system("start powerpnt")
    return "Abriendo PowerPoint."


def _abrir_spotify(params):
    os.system("start spotify")
    return "Abriendo Spotify."'''

content = content.replace(
    '''def _abrir_powerpoint(texto):
    os.system("start powerpnt")
    return "Abriendo PowerPoint."''',
    new_spotify
)

# Agregar "abrir_spotify" al DISPATCH
content = content.replace(
    '''    "abrir_powerpoint":      _abrir_powerpoint,
    "abrir_youtube":         _abrir_youtube,''',
    '''    "abrir_powerpoint":      _abrir_powerpoint,
    "abrir_spotify":         _abrir_spotify,
    "abrir_youtube":         _abrir_youtube,'''
)

# Escribir el archivo
with open('pc_control.py', 'w', encoding='utf-8') as f:
    f.write(content)

print("✓ Función _volumen_especifico actualizada")
print("✓ Función _abrir_spotify agregada")
print("✓ DISPATCH actualizado")
