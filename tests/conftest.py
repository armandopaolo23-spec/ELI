"""Configuración compartida de los tests.

Stub de dependencias pesadas (numpy, scipy, sounddevice, edge_tts, etc.)
que NO se ejecutan en los tests pero sí se importan en módulos que
queremos testear. Los tests cubren funciones puras (regex, splitters,
persistencia JSON); los stubs nunca se llaman de verdad.
"""

import sys
from pathlib import Path
from unittest.mock import MagicMock

# Permitir que `import cerebro`, `import hablar`, etc. resuelvan al
# código del proyecto cuando pytest se invoca desde la raíz.
RAIZ = Path(__file__).resolve().parent.parent
if str(RAIZ) not in sys.path:
    sys.path.insert(0, str(RAIZ))

# Stub de deps externas no instaladas en CI/sandbox de tests.
_DEPS_STUB = (
    "numpy",
    "scipy",
    "scipy.io",
    "scipy.io.wavfile",
    "scipy.signal",
    "sounddevice",
    "soundfile",
    "edge_tts",
    "pyautogui",
    "psutil",
    "speech_recognition",
)
for _mod in _DEPS_STUB:
    sys.modules.setdefault(_mod, MagicMock())
