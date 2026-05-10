"""Tests de la persistencia JSON de memoria.py."""

import json
from unittest.mock import patch

import pytest

import memoria as memoria_mod
from memoria import (
    actualizar_perfil,
    agregar_resumen,
    cargar_memoria,
    guardar_memoria,
    memoria_a_texto,
    MAX_RESUMENES,
)


@pytest.fixture
def archivo_temp(tmp_path, monkeypatch):
    """Apunta RUTA_MEMORIA a un archivo temporal aislado por test."""
    ruta = tmp_path / "memoria.json"
    monkeypatch.setattr(memoria_mod, "RUTA_MEMORIA", str(ruta))
    return ruta


class TestCargarMemoria:
    def test_archivo_inexistente_retorna_estructura_vacia(self, archivo_temp):
        # archivo_temp aún no existe.
        m = cargar_memoria()
        assert m == {"perfil": {}, "resumenes": []}

    def test_archivo_corrupto_retorna_vacio(self, archivo_temp):
        archivo_temp.write_text("{ esto no es JSON válido", encoding="utf-8")
        m = cargar_memoria()
        assert m == {"perfil": {}, "resumenes": []}

    def test_completa_estructura_minima(self, archivo_temp):
        # Falta "resumenes"; debe agregarlo.
        archivo_temp.write_text('{"perfil": {"nombre": "Paolo"}}', encoding="utf-8")
        m = cargar_memoria()
        assert m["perfil"] == {"nombre": "Paolo"}
        assert m["resumenes"] == []

    def test_roundtrip_save_load(self, archivo_temp):
        original = {
            "perfil": {"nombre": "Paolo", "ciudad": "Cajamarca"},
            "resumenes": [{"fecha": "2026-05-10 14:00", "contenido": "Hola"}],
        }
        guardar_memoria(original)
        cargada = cargar_memoria()
        assert cargada == original


class TestAgregarResumen:
    def test_agrega_uno(self, archivo_temp):
        m = {"perfil": {}, "resumenes": []}
        agregar_resumen(m, "Resumen de prueba")
        assert len(m["resumenes"]) == 1
        assert m["resumenes"][0]["contenido"] == "Resumen de prueba"
        assert "fecha" in m["resumenes"][0]

    def test_recorta_a_max(self, archivo_temp):
        m = {"perfil": {}, "resumenes": []}
        for i in range(MAX_RESUMENES + 5):
            agregar_resumen(m, f"resumen {i}")
        assert len(m["resumenes"]) == MAX_RESUMENES
        # Conserva los más recientes (los últimos i).
        contenidos = [r["contenido"] for r in m["resumenes"]]
        assert contenidos[-1] == f"resumen {MAX_RESUMENES + 4}"
        assert contenidos[0] == "resumen 5"  # los primeros 5 se descartaron


class TestActualizarPerfil:
    def test_agrega_clave_nueva(self):
        m = {"perfil": {}, "resumenes": []}
        actualizar_perfil(m, {"nombre": "Paolo"})
        assert m["perfil"]["nombre"] == "Paolo"

    def test_sobreescribe_clave_existente(self):
        m = {"perfil": {"ciudad": "Lima"}, "resumenes": []}
        actualizar_perfil(m, {"ciudad": "Cajamarca"})
        assert m["perfil"]["ciudad"] == "Cajamarca"

    def test_extiende_lista_sin_duplicados(self):
        m = {"perfil": {"notas": ["a", "b"]}, "resumenes": []}
        actualizar_perfil(m, {"notas": ["b", "c"]})
        assert m["perfil"]["notas"] == ["a", "b", "c"]

    def test_input_no_dict_se_ignora(self):
        m = {"perfil": {"nombre": "Paolo"}, "resumenes": []}
        actualizar_perfil(m, "no es un dict")
        assert m["perfil"] == {"nombre": "Paolo"}


class TestMemoriaATexto:
    def test_vacia_retorna_string_vacio(self):
        assert memoria_a_texto({"perfil": {}, "resumenes": []}) == ""

    def test_incluye_perfil(self):
        m = {"perfil": {"nombre": "Paolo"}, "resumenes": []}
        texto = memoria_a_texto(m)
        assert "DATOS DEL USUARIO" in texto
        assert "Paolo" in texto

    def test_incluye_solo_los_5_ultimos_resumenes(self):
        resumenes = [
            {"fecha": f"2026-05-{i:02d} 12:00", "contenido": f"resumen {i}"}
            for i in range(1, 11)
        ]
        m = {"perfil": {}, "resumenes": resumenes}
        texto = memoria_a_texto(m)
        # Cuento por las fechas (son únicas, sin riesgo de match parcial
        # como pasaría con "resumen 1" vs "resumen 10").
        for dia in range(1, 6):  # del 1 al 5: NO aparecen
            assert f"2026-05-0{dia}" not in texto
        for dia in range(6, 11):  # del 6 al 10: SÍ aparecen
            esperado = f"2026-05-0{dia}" if dia < 10 else "2026-05-10"
            assert esperado in texto

    def test_lista_en_perfil_se_muestra_separada_por_coma(self):
        m = {
            "perfil": {"notas": ["examen viernes", "modo oscuro"]},
            "resumenes": [],
        }
        texto = memoria_a_texto(m)
        assert "examen viernes, modo oscuro" in texto
