"""Tests para timing_decorator — medición de latencias p50/p95/p99."""

import time
import pytest
from logger import timing_decorator


class TestTimingDecorator:
    def test_retorna_resultado_original(self):
        @timing_decorator
        def sumar(a, b):
            return a + b

        assert sumar(2, 3) == 5

    def test_acumula_mediciones_en_historial(self):
        @timing_decorator
        def noop():
            pass

        for _ in range(5):
            noop()
        assert len(noop._historial) == 5

    def test_preserva_nombre_de_funcion(self):
        @timing_decorator
        def mi_funcion_con_nombre():
            pass

        assert mi_funcion_con_nombre.__name__ == "mi_funcion_con_nombre"

    def test_historial_accesible_en_wrapper(self):
        @timing_decorator
        def tarea():
            return 42

        tarea()
        assert len(tarea._historial) == 1
        assert tarea._historial[0] >= 0

    def test_historial_respeta_maxlen_100(self):
        @timing_decorator
        def rapida():
            pass

        for _ in range(105):
            rapida()
        assert len(rapida._historial) == 100

    def test_propaga_excepcion_del_original(self):
        @timing_decorator
        def falla():
            raise ValueError("error esperado")

        with pytest.raises(ValueError, match="error esperado"):
            falla()

    def test_no_registra_timing_si_excepcion(self):
        @timing_decorator
        def falla():
            raise RuntimeError("boom")

        try:
            falla()
        except RuntimeError:
            pass
        assert len(falla._historial) == 0

    def test_mide_tiempo_real_en_ms(self):
        @timing_decorator
        def lenta():
            time.sleep(0.05)

        lenta()
        assert lenta._historial[0] >= 40
