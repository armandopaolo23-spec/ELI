"""Tests para comandos de ventanas (wmctrl) y nuevas apps (terminal, vscode)."""

from __future__ import annotations

from unittest.mock import patch, MagicMock

import pytest

import sys
from pathlib import Path
RAIZ = Path(__file__).resolve().parent.parent
if str(RAIZ) not in sys.path:
    sys.path.insert(0, str(RAIZ))

import os_compat
from comandos import sistema, apps


# ============================================================
# os_compat.controlar_ventana_activa
# ============================================================

class TestControlarVentanaActiva:
    def test_minimizar_llama_wmctrl_hidden(self):
        with patch("os_compat.IS_LINUX", True), \
             patch("os_compat.shutil.which", return_value="/usr/bin/wmctrl"), \
             patch("os_compat.subprocess.Popen") as mock_popen:
            result = os_compat.controlar_ventana_activa("minimizar")
        assert result is True
        mock_popen.assert_called_once_with(
            ["wmctrl", "-r", ":ACTIVE:", "-b", "add,hidden"]
        )

    def test_maximizar_llama_wmctrl_maximized(self):
        with patch("os_compat.IS_LINUX", True), \
             patch("os_compat.shutil.which", return_value="/usr/bin/wmctrl"), \
             patch("os_compat.subprocess.Popen") as mock_popen:
            result = os_compat.controlar_ventana_activa("maximizar")
        assert result is True
        mock_popen.assert_called_once_with(
            ["wmctrl", "-r", ":ACTIVE:", "-b", "add,maximized_vert,maximized_horz"]
        )

    def test_cerrar_llama_wmctrl_close(self):
        with patch("os_compat.IS_LINUX", True), \
             patch("os_compat.shutil.which", return_value="/usr/bin/wmctrl"), \
             patch("os_compat.subprocess.Popen") as mock_popen:
            result = os_compat.controlar_ventana_activa("cerrar")
        assert result is True
        mock_popen.assert_called_once_with(["wmctrl", "-c", ":ACTIVE:"])

    def test_retorna_false_si_wmctrl_no_instalado(self):
        with patch("os_compat.IS_LINUX", True), \
             patch("os_compat.shutil.which", return_value=None):
            result = os_compat.controlar_ventana_activa("cerrar")
        assert result is False

    def test_retorna_false_en_windows(self):
        with patch("os_compat.IS_LINUX", False):
            result = os_compat.controlar_ventana_activa("cerrar")
        assert result is False

    def test_accion_desconocida_retorna_false(self):
        with patch("os_compat.IS_LINUX", True), \
             patch("os_compat.shutil.which", return_value="/usr/bin/wmctrl"):
            result = os_compat.controlar_ventana_activa("volar")
        assert result is False

    def test_oserror_retorna_false(self):
        with patch("os_compat.IS_LINUX", True), \
             patch("os_compat.shutil.which", return_value="/usr/bin/wmctrl"), \
             patch("os_compat.subprocess.Popen", side_effect=OSError("fallo")):
            result = os_compat.controlar_ventana_activa("cerrar")
        assert result is False


# ============================================================
# comandos/sistema.py — handlers de ventanas
# ============================================================

class TestComandosVentanas:
    def test_minimizar_ventana_ok(self):
        with patch("os_compat.controlar_ventana_activa", return_value=True):
            msg = sistema._minimizar_ventana({})
        assert "minimizada" in msg.lower()

    def test_minimizar_ventana_falla(self):
        with patch("os_compat.controlar_ventana_activa", return_value=False):
            msg = sistema._minimizar_ventana({})
        assert "wmctrl" in msg.lower()

    def test_maximizar_ventana_ok(self):
        with patch("os_compat.controlar_ventana_activa", return_value=True):
            msg = sistema._maximizar_ventana({})
        assert "maximizada" in msg.lower()

    def test_maximizar_ventana_falla(self):
        with patch("os_compat.controlar_ventana_activa", return_value=False):
            msg = sistema._maximizar_ventana({})
        assert "wmctrl" in msg.lower()

    def test_cerrar_ventana_ok(self):
        with patch("os_compat.controlar_ventana_activa", return_value=True):
            msg = sistema._cerrar_ventana({})
        assert "cerrada" in msg.lower()

    def test_cerrar_ventana_falla(self):
        with patch("os_compat.controlar_ventana_activa", return_value=False):
            msg = sistema._cerrar_ventana({})
        assert "wmctrl" in msg.lower()

    def test_minimizar_pasa_accion_correcta(self):
        with patch("os_compat.controlar_ventana_activa", return_value=True) as mock_ctrl:
            sistema._minimizar_ventana({})
        mock_ctrl.assert_called_once_with("minimizar")

    def test_maximizar_pasa_accion_correcta(self):
        with patch("os_compat.controlar_ventana_activa", return_value=True) as mock_ctrl:
            sistema._maximizar_ventana({})
        mock_ctrl.assert_called_once_with("maximizar")

    def test_cerrar_pasa_accion_correcta(self):
        with patch("os_compat.controlar_ventana_activa", return_value=True) as mock_ctrl:
            sistema._cerrar_ventana({})
        mock_ctrl.assert_called_once_with("cerrar")

    def test_dispatch_contiene_comandos_ventanas(self):
        assert "minimizar_ventana" in sistema.DISPATCH
        assert "maximizar_ventana" in sistema.DISPATCH
        assert "cerrar_ventana" in sistema.DISPATCH


# ============================================================
# comandos/apps.py — terminal y vscode
# ============================================================

class TestComandosApps:
    def test_abrir_terminal_ok(self):
        with patch("os_compat.abrir_app", return_value=True):
            msg = apps._abrir_terminal({})
        assert "terminal" in msg.lower()

    def test_abrir_terminal_falla(self):
        with patch("os_compat.abrir_app", return_value=False):
            msg = apps._abrir_terminal({})
        assert "terminal" in msg.lower()
        assert "no" in msg.lower()

    def test_abrir_vscode_ok(self):
        with patch("os_compat.abrir_app", return_value=True):
            msg = apps._abrir_vscode({})
        assert "visual studio code" in msg.lower() or "code" in msg.lower()

    def test_abrir_vscode_falla(self):
        with patch("os_compat.abrir_app", return_value=False):
            msg = apps._abrir_vscode({})
        assert "no" in msg.lower()

    def test_terminal_usa_nombre_logico_correcto(self):
        with patch("os_compat.abrir_app", return_value=True) as mock_app:
            apps._abrir_terminal({})
        mock_app.assert_called_once_with("terminal")

    def test_vscode_usa_nombre_logico_correcto(self):
        with patch("os_compat.abrir_app", return_value=True) as mock_app:
            apps._abrir_vscode({})
        mock_app.assert_called_once_with("vscode")

    def test_dispatch_contiene_terminal_y_vscode(self):
        assert "abrir_terminal" in apps.DISPATCH
        assert "abrir_vscode" in apps.DISPATCH


# ============================================================
# Integración: DISPATCH global en comandos/__init__
# ============================================================

class TestDispatchGlobal:
    def test_comandos_ventanas_en_dispatch_global(self):
        from comandos import DISPATCH
        for cmd in ("minimizar_ventana", "maximizar_ventana", "cerrar_ventana"):
            assert cmd in DISPATCH, f"'{cmd}' no está en DISPATCH global"

    def test_apps_nuevas_en_dispatch_global(self):
        from comandos import DISPATCH
        for cmd in ("abrir_terminal", "abrir_vscode"):
            assert cmd in DISPATCH, f"'{cmd}' no está en DISPATCH global"

    def test_ejecutar_comando_minimizar(self):
        from comandos import ejecutar_comando
        with patch("os_compat.controlar_ventana_activa", return_value=True):
            result = ejecutar_comando("minimizar_ventana", {})
        assert result is not None
        assert "minimizada" in result.lower()

    def test_ejecutar_comando_abrir_terminal(self):
        from comandos import ejecutar_comando
        with patch("os_compat.abrir_app", return_value=True):
            result = ejecutar_comando("abrir_terminal", {})
        assert result is not None
        assert "terminal" in result.lower()
