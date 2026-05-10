"""Tests del filtro anti-falsos-positivos del wake word."""

import pytest

from wake_word import _es_wake_word, _levenshtein, _normalizar


class TestLevenshtein:
    def test_iguales(self):
        assert _levenshtein("eli", "eli") == 0

    def test_vacios(self):
        assert _levenshtein("", "eli") == 3
        assert _levenshtein("eli", "") == 3
        assert _levenshtein("", "") == 0

    def test_insercion(self):
        assert _levenshtein("eli", "elli") == 1
        assert _levenshtein("eli", "heli") == 1

    def test_sustitucion(self):
        assert _levenshtein("eli", "ali") == 1

    def test_diferencia_grande(self):
        # "delin" → "eli" requiere borrar 'd' y 'n' (2 ops).
        assert _levenshtein("eli", "delin") == 2
        assert _levenshtein("eli", "elite") == 2


class TestNormalizar:
    def test_minuscula(self):
        assert _normalizar("ELI") == "eli"

    def test_quita_tildes(self):
        assert _normalizar("Elí") == "eli"

    def test_dieresis(self):
        assert _normalizar("Müller") == "muller"

    def test_string_vacio(self):
        assert _normalizar("") == ""


# Tabla de casos copiada del bloque __main__ original de wake_word.py,
# más algunos extra. Si alguno cambia de comportamiento, falla aquí.
CASOS_WAKE = [
    # (texto, debe_aceptar)
    ("eli", True),
    ("Elí", True),
    ("hey eli", True),
    ("oye eli", True),
    ("ey eli", True),
    ("heli", True),           # distancia 1
    ("elli", True),           # distancia 1
    ("eli hola", True),       # corto + contiene "eli"
    ("hey elli", True),       # frase similar

    ("elite", False),         # distancia 2
    ("delin", False),         # distancia 3
    ("celis", False),         # distancia 2
    ("jajaja", False),        # nada que ver
    ("belly", False),         # distancia 2
    ("estaba hablando con mi amigo sobre eli", False),  # frase larga
    ("la película de ayer estuvo genial", False),
    ("", False),
]


class TestEsWakeWord:
    @pytest.mark.parametrize("texto,esperado", CASOS_WAKE)
    def test_casos_tabla(self, texto, esperado):
        assert _es_wake_word(texto) is esperado
