"""Tests del parsing de streaming de cerebro.py.

Cubre las funciones que extraen JSON parcial del stream de Ollama:
- _intentar_extraer_respuesta_temprana: detecta cuándo el campo
  "respuesta" ya está completo dentro de una conversación
  (comando=ninguno) para disparar TTS antes de cerrar el JSON.
- _intentar_parseo_temprano: detecta JSON completo y parseable.
- _normalizar_resultado: normaliza distintas formas que Ollama puede
  emitir a la lista uniforme que main.py consume.
"""

import pytest

from cerebro import (
    _intentar_extraer_respuesta_temprana,
    _intentar_parseo_temprano,
    _normalizar_resultado,
)


# ============================================================
# _intentar_extraer_respuesta_temprana
# ============================================================

class TestExtraccionTemprana:
    def test_conversacion_completa(self):
        texto = '{"comando": "ninguno", "respuesta": "Hola humano."}'
        assert _intentar_extraer_respuesta_temprana(texto) == "Hola humano."

    def test_orden_campos_invertido(self):
        # qwen3 a veces emite respuesta primero.
        texto = '{"respuesta": "Saludos.", "comando": "ninguno"}'
        assert _intentar_extraer_respuesta_temprana(texto) == "Saludos."

    def test_respuesta_vacia_no_dispara(self):
        # Stream a medio emitir: respuesta aún no tiene contenido.
        texto = '{"comando": "ninguno", "respuesta": ""}'
        assert _intentar_extraer_respuesta_temprana(texto) is None

    def test_respuesta_sin_cerrar_no_dispara(self):
        # Comilla de cierre todavía no llegó.
        texto = '{"comando": "ninguno", "respuesta": "Hola hum'
        assert _intentar_extraer_respuesta_temprana(texto) is None

    def test_comando_no_ninguno_no_dispara(self):
        # Si es comando real, NO debe disparar TTS de "respuesta".
        texto = '{"comando": "abrir_chrome", "parametros": {}}'
        assert _intentar_extraer_respuesta_temprana(texto) is None

    def test_sin_comando_aun_no_dispara(self):
        # El campo "comando" no se ha emitido todavía.
        texto = '{"respuesta": "Algo dice."'
        assert _intentar_extraer_respuesta_temprana(texto) is None

    def test_think_block_pendiente_espera(self):
        # qwen3 emite <think>...</think> antes del JSON.
        texto = '<think>analizando'
        assert _intentar_extraer_respuesta_temprana(texto) is None

    def test_think_block_cerrado_extrae(self):
        texto = (
            '<think>el usuario saluda</think>'
            '{"comando": "ninguno", "respuesta": "Sí, hola."}'
        )
        assert _intentar_extraer_respuesta_temprana(texto) == "Sí, hola."

    def test_comilla_escapada_no_corta_prematuro(self):
        # \" dentro del valor no debe terminar la captura.
        texto = '{"comando": "ninguno", "respuesta": "Dijo \\"hola\\" entonces."}'
        resultado = _intentar_extraer_respuesta_temprana(texto)
        assert resultado == 'Dijo "hola" entonces.'

    def test_decodifica_unicode_escape(self):
        texto = '{"comando": "ninguno", "respuesta": "C\\u00f3mo est\\u00e1s"}'
        assert _intentar_extraer_respuesta_temprana(texto) == "Cómo estás"

    def test_decodifica_newline_escape(self):
        texto = '{"comando": "ninguno", "respuesta": "Linea 1\\nLinea 2"}'
        assert _intentar_extraer_respuesta_temprana(texto) == "Linea 1\nLinea 2"

    def test_respuesta_con_espacios_alrededor_de_dos_puntos(self):
        texto = '{"comando":"ninguno","respuesta":  "Sin espacios."}'
        assert _intentar_extraer_respuesta_temprana(texto) == "Sin espacios."

    def test_respuesta_solo_whitespace_no_dispara(self):
        texto = '{"comando": "ninguno", "respuesta": "   "}'
        assert _intentar_extraer_respuesta_temprana(texto) is None


# ============================================================
# _intentar_parseo_temprano
# ============================================================

class TestParseoTemprano:
    def test_json_incompleto_retorna_none(self):
        assert _intentar_parseo_temprano('{"comando": "abrir_chrome"') is None

    def test_solo_think_sin_json_retorna_none(self):
        assert _intentar_parseo_temprano("<think>algo</think>") is None

    def test_brackets_desbalanceados_retorna_none(self):
        # Hay un `}` final pero los internos no balancean.
        assert _intentar_parseo_temprano('{"a": {"b": 1}') is None

    def test_comando_simple(self):
        resultado = _intentar_parseo_temprano(
            '{"comando": "abrir_chrome", "parametros": {}}'
        )
        assert resultado == [{"comando": "abrir_chrome", "parametros": {}}]

    def test_conversacion_simple(self):
        resultado = _intentar_parseo_temprano(
            '{"comando": "ninguno", "respuesta": "Hola."}'
        )
        assert len(resultado) == 1
        assert resultado[0]["comando"] == "ninguno"
        assert resultado[0]["respuesta"] == "Hola."

    def test_comandos_multiples(self):
        json_str = (
            '{"comandos": ['
            '{"comando": "abrir_chrome", "parametros": {}},'
            '{"comando": "buscar_google", "parametros": {"busqueda": "x"}}'
            "]}"
        )
        resultado = _intentar_parseo_temprano(json_str)
        assert len(resultado) == 2
        assert resultado[0]["comando"] == "abrir_chrome"
        assert resultado[1]["parametros"]["busqueda"] == "x"

    def test_con_think_block_lo_strippea(self):
        resultado = _intentar_parseo_temprano(
            '<think>el usuario quiere abrir chrome</think>'
            '{"comando": "abrir_chrome", "parametros": {}}'
        )
        assert resultado == [{"comando": "abrir_chrome", "parametros": {}}]

    def test_think_abierto_sin_cerrar_espera(self):
        # Aún emitiendo el bloque de pensamiento.
        assert _intentar_parseo_temprano("<think>analizando...") is None


# ============================================================
# _normalizar_resultado
# ============================================================

class TestNormalizarResultado:
    def test_un_comando_agrega_parametros_vacios(self):
        resultado = _normalizar_resultado({"comando": "abrir_chrome"})
        assert resultado == [{"comando": "abrir_chrome", "parametros": {}}]

    def test_ninguno_sin_respuesta_pone_default(self):
        resultado = _normalizar_resultado({"comando": "ninguno"})
        assert resultado[0]["respuesta"] == "(sin respuesta)"

    def test_multiples_comandos_se_limitan_a_5(self):
        comandos = [{"comando": f"cmd_{i}", "parametros": {}} for i in range(10)]
        resultado = _normalizar_resultado({"comandos": comandos})
        assert len(resultado) == 5

    def test_comandos_lista_vacia_fallback(self):
        resultado = _normalizar_resultado({"comandos": []})
        assert len(resultado) == 1
        assert resultado[0]["comando"] == "ninguno"

    def test_respuesta_anidada_se_desempaca(self):
        # Caso patológico: el modelo mete JSON dentro del campo respuesta.
        anidado = {
            "comando": "ninguno",
            "respuesta": '{"respuesta": "el valor real"}',
        }
        resultado = _normalizar_resultado(anidado)
        assert resultado[0]["respuesta"] == "el valor real"

    def test_sin_clave_comando_fallback(self):
        resultado = _normalizar_resultado({"otro_campo": 42})
        assert resultado[0]["comando"] == "ninguno"
