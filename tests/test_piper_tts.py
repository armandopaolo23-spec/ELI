"""Tests para piper_tts — TTS local con Piper ONNX."""

from unittest.mock import MagicMock, patch
import numpy as np
import pytest
import piper_tts


@pytest.fixture(autouse=True)
def reset_singleton():
    piper_tts._voz = None
    yield
    piper_tts._voz = None


def _make_mock_voz(sample_rate=22050, audio=b"\x00\x01"):
    voz = MagicMock()
    voz.config.sample_rate = sample_rate
    
    # Mock AudioChunk con audio_int16_array
    chunk = MagicMock()
    chunk.audio_int16_array = np.frombuffer(audio, dtype=np.int16)
    
    voz.synthesize.return_value = iter([chunk])
    return voz


class TestPrecarga:
    def test_carga_voz_piper(self):
        with patch("pathlib.Path.exists", return_value=True):
            piper_tts.precarga()
        assert piper_tts._voz is not None

    def test_es_idempotente(self):
        piper_tts._voz = _make_mock_voz()
        original = piper_tts._voz
        with patch("pathlib.Path.exists", return_value=True):
            piper_tts.precarga()
        assert piper_tts._voz is original

    def test_lanza_si_modelo_no_existe(self):
        with patch("config.PIPER_MODELO_PATH", "/path/que/no/existe.onnx"):
            with pytest.raises(FileNotFoundError):
                piper_tts.precarga()

class TestSintetizar:
    def test_texto_vacio_retorna_none(self):
        mock_voz = MagicMock()
        mock_voz.synthesize_stream_raw.return_value = iter([])
        piper_tts._voz = mock_voz
        assert piper_tts.sintetizar("") is None

    def test_retorna_tupla_con_dos_elementos(self):
        piper_tts._voz = _make_mock_voz(sample_rate=22050)
        result = piper_tts.sintetizar("hola mundo")
        assert result is not None
        assert len(result) == 2

    def test_sample_rate_del_modelo(self):
        piper_tts._voz = _make_mock_voz(sample_rate=16000)
        _, sr = piper_tts.sintetizar("hola")
        assert sr == 16000

    def test_llama_precarga_si_sin_voz(self):
        assert piper_tts._voz is None
        mock_voz = _make_mock_voz()

        def fake_precarga():
            piper_tts._voz = mock_voz

        with patch.object(piper_tts, "precarga", side_effect=fake_precarga):
            piper_tts.sintetizar("hola")
        assert piper_tts._voz is not None

    def test_usa_length_scale_por_speed(self):
        import config as cfg
        piper_tts._voz = _make_mock_voz()
        piper_tts.sintetizar("hola")
        _, kwargs = piper_tts._voz.synthesize.call_args
        expected = 1.0 / cfg.PIPER_SPEED if cfg.PIPER_SPEED > 0 else 1.0
        assert abs(kwargs["length_scale"] - expected) < 1e-9
