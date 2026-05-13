"""Tests de integración del pipeline de voz local (VAD → STT → LLM → TTS)."""

import threading
from unittest.mock import MagicMock, patch
import numpy as np
import pytest

import whisper_stt
import vad_detector
import piper_tts


@pytest.fixture(autouse=True)
def reset_singletons():
    whisper_stt._modelo = None
    vad_detector._modelo = None
    vad_detector._stream = None
    piper_tts._voz = None
    yield
    whisper_stt._modelo = None
    vad_detector._modelo = None
    vad_detector._stream = None
    piper_tts._voz = None


class TestPipelineSTT:
    def test_transcribe_texto_simple(self):
        seg = MagicMock()
        seg.text = "hola eli"
        mock_m = MagicMock()
        mock_m.transcribe.return_value = ([seg], MagicMock())
        whisper_stt._modelo = mock_m
        assert whisper_stt.transcribir(MagicMock()) == "hola eli"

    def test_texto_retornado_en_minusculas(self):
        seg = MagicMock()
        seg.text = "TEXTO EN MAYUSCULAS"
        mock_m = MagicMock()
        mock_m.transcribe.return_value = ([seg], MagicMock())
        whisper_stt._modelo = mock_m
        resultado = whisper_stt.transcribir(MagicMock())
        assert resultado == resultado.lower()

    def test_multiples_segmentos_concatenados(self):
        segs = [MagicMock() for _ in range(3)]
        for i, s in enumerate(segs):
            s.text = f"seg{i}"
        mock_m = MagicMock()
        mock_m.transcribe.return_value = (segs, MagicMock())
        whisper_stt._modelo = mock_m
        assert whisper_stt.transcribir(MagicMock()) == "seg0 seg1 seg2"


class TestPipelineTTS:
    def test_sintetiza_y_retorna_audio(self):
        chunk = MagicMock()
        chunk.audio_int16_array = np.array([0, 1, 2, 3], dtype=np.int16)
        
        voz = MagicMock()
        voz.config.sample_rate = 22050
        voz.synthesize.return_value = iter([chunk])
        piper_tts._voz = voz
        result = piper_tts.sintetizar("texto de prueba")
        assert result is not None

    def test_texto_vacio_retorna_none(self):
        voz = MagicMock()
        voz.synthesize.return_value = iter([])
        piper_tts._voz = voz
        assert piper_tts.sintetizar("") is None

    def test_sample_rate_correcto_para_cada_modelo(self):
        for sr in [16000, 22050, 44100]:
            chunk = MagicMock()
            chunk.audio_int16_array = np.array([1], dtype=np.int16)
            
            voz = MagicMock()
            voz.config.sample_rate = sr
            voz.synthesize.return_value = iter([chunk])
            piper_tts._voz = voz
            _, tasa = piper_tts.sintetizar("test")
            assert tasa == sr


class TestInicializacionParalela:
    def test_precargas_en_hilos_sin_deadlock(self):
        mock_whisper = MagicMock()
        mock_vad = MagicMock()
        mock_vad_iter = MagicMock()
        mock_voz = MagicMock()
        mock_voz.config.sample_rate = 22050

        with patch("faster_whisper.WhisperModel", return_value=mock_whisper), \
             patch("silero_vad.load_silero_vad", return_value=mock_vad), \
             patch("silero_vad.VADIterator", return_value=mock_vad_iter), \
             patch("pathlib.Path.exists", return_value=True), \
             patch("piper.voice.PiperVoice") as PV:
            PV.load.return_value = mock_voz
            hilos = [
                threading.Thread(target=whisper_stt.precarga),
                threading.Thread(target=vad_detector.precarga),
                threading.Thread(target=piper_tts.precarga),
            ]
            for h in hilos:
                h.start()
            for h in hilos:
                h.join(timeout=5.0)

        assert all(not h.is_alive() for h in hilos), "Hilo de precarga bloqueado"

    def test_singletons_son_instancias_independientes(self):
        whisper_stt._modelo = MagicMock()
        piper_tts._voz = MagicMock()
        vad_detector._modelo = MagicMock()
        assert whisper_stt._modelo is not piper_tts._voz
        assert piper_tts._voz is not vad_detector._modelo
