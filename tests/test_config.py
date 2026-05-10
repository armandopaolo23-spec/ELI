"""Tests del helper _env de config.py: parsing de env vars seguro."""

import os

import pytest

from config import _env


class TestEnv:
    def test_default_cuando_no_hay_env(self, monkeypatch):
        monkeypatch.delenv("ELI_FOO", raising=False)
        assert _env("FOO", 42, int) == 42

    def test_lee_int_valido(self, monkeypatch):
        monkeypatch.setenv("ELI_FOO", "120")
        assert _env("FOO", 60, int) == 120

    def test_lee_float_valido(self, monkeypatch):
        monkeypatch.setenv("ELI_FOO", "0.005")
        assert _env("FOO", 0.008, float) == 0.005

    def test_int_invalido_usa_default(self, monkeypatch):
        monkeypatch.setenv("ELI_FOO", "no-numero")
        assert _env("FOO", 60, int) == 60

    def test_string_pasa_directo(self, monkeypatch):
        monkeypatch.setenv("ELI_VOZ", "es-ES-AlvaroNeural")
        assert _env("VOZ", "default", str) == "es-ES-AlvaroNeural"

    def test_bool_true_aceptado(self, monkeypatch):
        for valor in ("1", "true", "True", "yes", "on"):
            monkeypatch.setenv("ELI_FOO", valor)
            assert _env("FOO", False, bool) is True

    def test_bool_false_default(self, monkeypatch):
        monkeypatch.setenv("ELI_FOO", "0")
        assert _env("FOO", True, bool) is False

    def test_string_vacio_se_acepta(self, monkeypatch):
        # Un string vacío explícito no es None — se devuelve.
        monkeypatch.setenv("ELI_FOO", "")
        assert _env("FOO", "default", str) == ""
