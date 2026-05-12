"""Tests para vad_detector — detección de habla con Silero VAD."""

import queue
from unittest.mock import MagicMock, patch
import pytest
import vad_detector


@pytest.fixture(autouse=True)
def reset_singleton():
    vad_detector._modelo = None
    vad_detector._vad_iterator = None
    vad_detector._stream = None
    yield
    vad_detector._modelo = None
    vad_detector._vad_iterator = None
    vad_detector._stream = None


def _make_mock_block(size=512):
    """Mock de bloque de audio que pasa la verificación de tamaño."""
    block_1d = MagicMock()
    block_1d.__len__ = MagicMock(return_value=size)
    block = MagicMock()
    block.flatten.return_value.astype.return_value = block_1d
    return block


class TestConstantes:
    def test_samplerate_es_16000(self):
        assert vad_detector.SAMPLERATE == 16000

    def test_blocksize_es_512(self):
        assert vad_detector.BLOCKSIZE == 512


class TestPrecarga:
    def test_carga_modelo_silero(self):
        mock_modelo = MagicMock()
        mock_iter = MagicMock()
        with patch("silero_vad.load_silero_vad", return_value=mock_modelo), \
             patch("silero_vad.VADIterator", return_value=mock_iter):
            vad_detector.precarga()
        assert vad_detector._modelo is mock_modelo
        assert vad_detector._vad_iterator is mock_iter

    def test_es_idempotente(self):
        vad_detector._modelo = MagicMock()
        vad_detector._vad_iterator = MagicMock()
        with patch("silero_vad.load_silero_vad") as fn:
            vad_detector.precarga()
        fn.assert_not_called()


class TestCalibrarStream:
    def test_crea_inputstream(self):
        mock_stream = MagicMock()
        with patch("sounddevice.InputStream", return_value=mock_stream), \
             patch("vad_detector.time") as mock_time:
            mock_time.time.return_value = 0.0
            mock_time.sleep = MagicMock()
            vad_detector.calibrar_stream()
        assert vad_detector._stream is mock_stream

    def test_es_idempotente(self):
        existing = MagicMock()
        vad_detector._stream = existing
        with patch("sounddevice.InputStream") as cls:
            vad_detector.calibrar_stream()
        cls.assert_not_called()


class TestCallback:
    def test_agrega_copia_a_cola(self):
        cola = queue.Queue()
        with patch.object(vad_detector, "_q", cola):
            datos = MagicMock()
            vad_detector._callback(datos, 512, None, None)
        assert not cola.empty()
        datos.copy.assert_called_once()


class TestDetectarAudio:
    def test_retorna_none_en_timeout(self):
        vad_detector._modelo = MagicMock()
        vad_detector._stream = MagicMock()
        vad_iter = MagicMock(return_value=None)
        vad_detector._vad_iterator = vad_iter

        mock_q = MagicMock()
        mock_q.empty.return_value = True
        mock_q.get.return_value = _make_mock_block()

        with patch.object(vad_detector, "_q", mock_q), \
             patch("vad_detector.time") as mock_time:
            mock_time.time.side_effect = [0.0, 9999.0]
            resultado = vad_detector.detectar_audio()

        assert resultado is None

    def test_retorna_array_al_detectar_habla(self):
        vad_detector._modelo = MagicMock()
        vad_detector._stream = MagicMock()

        vad_iter = MagicMock()
        vad_iter.side_effect = [{"start": 0}, None, {"end": 1}]
        vad_detector._vad_iterator = vad_iter

        mock_q = MagicMock()
        mock_q.empty.return_value = True
        mock_q.get.return_value = _make_mock_block()

        with patch.object(vad_detector, "_q", mock_q), \
             patch("vad_detector.time") as mock_time:
            mock_time.time.return_value = 0.0
            resultado = vad_detector.detectar_audio()

        assert resultado is not None

    def test_llama_precarga_si_sin_modelo(self):
        assert vad_detector._modelo is None
        mock_modelo = MagicMock()
        mock_vad_iter = MagicMock(return_value=None)
        vad_detector._stream = MagicMock()

        mock_q = MagicMock()
        mock_q.empty.return_value = True
        mock_q.get.return_value = _make_mock_block()

        with patch("silero_vad.load_silero_vad", return_value=mock_modelo), \
             patch("silero_vad.VADIterator", return_value=mock_vad_iter), \
             patch.object(vad_detector, "_q", mock_q), \
             patch("vad_detector.time") as mock_time:
            mock_time.time.side_effect = [0.0, 9999.0]
            vad_detector.detectar_audio()

        assert vad_detector._modelo is not None
