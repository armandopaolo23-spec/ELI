"""Tests para whisper_stt — STT local con faster-whisper."""

from unittest.mock import MagicMock, patch
import pytest
import whisper_stt


@pytest.fixture(autouse=True)
def reset_singleton():
    whisper_stt._modelo = None
    yield
    whisper_stt._modelo = None


def _make_modelo(texto="hola mundo"):
    modelo = MagicMock()
    seg = MagicMock()
    seg.text = texto
    modelo.transcribe.return_value = ([seg], MagicMock())
    return modelo


class TestPrecarga:
    def test_carga_modelo_en_gpu(self):
        mock_m = MagicMock()
        with patch("faster_whisper.WhisperModel", return_value=mock_m):
            whisper_stt.precarga()
        assert whisper_stt._modelo is mock_m

    def test_es_idempotente(self):
        mock_m = _make_modelo()
        whisper_stt._modelo = mock_m
        with patch("faster_whisper.WhisperModel") as cls:
            whisper_stt.precarga()
        cls.assert_not_called()

    def test_doble_precarga_mantiene_instancia(self):
        mock_m = MagicMock()
        with patch("faster_whisper.WhisperModel", return_value=mock_m):
            whisper_stt.precarga()
            primera = whisper_stt._modelo
            whisper_stt.precarga()
        assert whisper_stt._modelo is primera


class TestTranscribir:
    def test_retorna_texto_en_minusculas(self):
        whisper_stt._modelo = _make_modelo("HOLA MUNDO")
        assert whisper_stt.transcribir(MagicMock()) == "hola mundo"

    def test_une_segmentos_con_espacio(self):
        modelo = MagicMock()
        seg1, seg2 = MagicMock(), MagicMock()
        seg1.text = "uno"
        seg2.text = "dos"
        modelo.transcribe.return_value = ([seg1, seg2], MagicMock())
        whisper_stt._modelo = modelo
        assert whisper_stt.transcribir(MagicMock()) == "uno dos"

    def test_segmentos_vacios_retorna_cadena_vacia(self):
        modelo = MagicMock()
        modelo.transcribe.return_value = ([], MagicMock())
        whisper_stt._modelo = modelo
        assert whisper_stt.transcribir(MagicMock()) == ""

    def test_llama_precarga_si_sin_modelo(self):
        assert whisper_stt._modelo is None
        mock_m = _make_modelo()
        with patch("faster_whisper.WhisperModel", return_value=mock_m):
            whisper_stt.transcribir(MagicMock())
        assert whisper_stt._modelo is not None

    def test_pasa_idioma_a_transcribe(self):
        import config as cfg
        whisper_stt._modelo = _make_modelo()
        whisper_stt.transcribir(MagicMock())
        _, kwargs = whisper_stt._modelo.transcribe.call_args
        assert kwargs["language"] == cfg.WHISPER_IDIOMA

    def test_pasa_beam_size_a_transcribe(self):
        import config as cfg
        whisper_stt._modelo = _make_modelo()
        whisper_stt.transcribir(MagicMock())
        _, kwargs = whisper_stt._modelo.transcribe.call_args
        assert kwargs["beam_size"] == cfg.WHISPER_BEAM_SIZE

    def test_strip_espacios_en_resultado(self):
        modelo = MagicMock()
        seg = MagicMock()
        seg.text = "  hola  "
        modelo.transcribe.return_value = ([seg], MagicMock())
        whisper_stt._modelo = modelo
        assert whisper_stt.transcribir(MagicMock()) == "hola"
