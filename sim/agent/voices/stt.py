"""Sherpa-ONNX STT plugin for LiveKit Agents.

Local, offline speech-to-text using Sherpa-ONNX streaming models.
Supports Chinese + English bilingual recognition.

Usage:
    stt = SherpaOnnxSTT(model_dir="sherpa-onnx-streaming-zipformer-bilingual-zh-en-2023-02-20")
    session = AgentSession(stt=stt, ...)

Models:
    Download from https://github.com/k2-fsa/sherpa-onnx/releases/download/asr-models/
    - Bilingual: sherpa-onnx-streaming-zipformer-bilingual-zh-en-2023-02-20.tar.bz2
"""

import logging
from pathlib import Path

logger = logging.getLogger("pupster.stt")

try:
    import numpy as np
except ImportError:
    np = None  # type: ignore

try:
    import sherpa_onnx
except ImportError:
    sherpa_onnx = None  # type: ignore


def _require_deps():
    from livekit.agents import stt as _stt
    if sherpa_onnx is None:
        raise ImportError("sherpa-onnx is required. Install with: pip install sherpa-onnx")
    if np is None:
        raise ImportError("numpy is required. Install with: pip install numpy")
    return _stt


class SherpaOnnxStream:
    """Streaming recognition using Sherpa-ONNX OnlineRecognizer."""

    def __init__(self, stt_impl, *, language=None, conn_options=None):
        from livekit.agents import stt
        self._stt_impl = stt_impl
        self._language = language
        self._stream = stt.RecognizeStream(stt_impl, conn_options=conn_options)

    @property
    def _input_ch(self):
        return self._stream._input_ch

    @property
    def _event_ch(self):
        return self._stream._event_ch

    async def _run(self):
        from livekit.agents import stt

        recognizer = self._stt_impl._recognizer
        stream = recognizer.create_stream()

        async for frame in self._input_ch:
            audio_data = frame.frame.to_ndarray()
            if audio_data.ndim == 2:
                audio_data = audio_data.mean(axis=1)
            audio_float = audio_data.astype(np.float32) / 32768.0

            stream.accept_waveform(audio_float)
            while recognizer.is_ready(stream):
                recognizer.decode_stream(stream)
                result = recognizer.get_result(stream)
                if result:
                    text = result.strip()
                    if text:
                        event = stt.SpeechEvent(
                            type=stt.SpeechEventType.INTERIM_TRANSCRIPT,
                            alternatives=[stt.SpeechData(text=text, confidence=1.0, language="")],
                        )
                        self._event_ch.send(event)

        # Finalize
        recognizer.input_finished()
        while recognizer.is_ready(stream):
            recognizer.decode_stream(stream)
            result = recognizer.get_result(stream)
            if result:
                text = result.strip()
                if text:
                    event = stt.SpeechEvent(
                        type=stt.SpeechEventType.FINAL_TRANSCRIPT,
                        alternatives=[stt.SpeechData(text=text, confidence=1.0, language="")],
                    )
                    self._event_ch.send(event)

        self._event_ch.send(stt.SpeechEvent(type=stt.SpeechEventType.END_OF_SPEECH))


class SherpaOnnxSTT:
    """Local Sherpa-ONNX STT implementation compatible with LiveKit Agents."""

    def __init__(self, model_dir: str | Path, *, sample_rate: int = 16000):
        _stt = _require_deps()
        self._stt_module = _stt

        model_dir = Path(model_dir)
        if not model_dir.exists():
            raise FileNotFoundError(
                f"Model directory not found: {model_dir}\n"
                "Download from: "
                "https://github.com/k2-fsa/sherpa-onnx/releases/download/asr-models/"
                "sherpa-onnx-streaming-zipformer-bilingual-zh-en-2023-02-20.tar.bz2"
            )

        self._sample_rate = sample_rate
        self._recognizer = self._create_recognizer(model_dir)
        logger.info(f"Sherpa-ONNX STT loaded from {model_dir}")

    def _create_recognizer(self, model_dir: Path):
        from sherpa_onnx.online_recognizer import OnlineRecognizer

        encoder = sorted(model_dir.glob("encoder*.onnx"))[0]
        decoder = sorted(model_dir.glob("decoder*.onnx"))[0]
        joiner = sorted(model_dir.glob("joiner*.onnx"))[0]
        tokens = sorted(model_dir.glob("tokens.txt"))[0]

        logger.info(f"  encoder: {encoder.name}")
        logger.info(f"  decoder: {decoder.name}")
        logger.info(f"  joiner:  {joiner.name}")
        logger.info(f"  tokens:  {tokens.name}")

        return OnlineRecognizer.from_transducer(
            tokens=str(tokens),
            encoder=str(encoder),
            decoder=str(decoder),
            joiner=str(joiner),
            num_threads=2,
            sample_rate=self._sample_rate,
            feature_dim=80,
            enable_endpoint_detection=True,
            rule1_min_trailing_silence=0.5,
            rule2_min_trailing_silence=1.2,
            rule3_min_utterance_length=20.0,
            decoding_method="greedy_search",
        )

    @property
    def sample_rate(self) -> int:
        return self._sample_rate

    @property
    def model(self) -> str:
        return "sherpa-onnx-streaming-zipformer-bilingual-zh-en"

    @property
    def provider(self) -> str:
        return "sherpa-onnx-local"

    def stream(self, *, language=None, conn_options=None):
        return SherpaOnnxStream(self, language=language, conn_options=conn_options)

    async def _recognize_impl(self, buffer, *, language=None, conn_options=None):
        raise NotImplementedError(
            "Only streaming recognition is supported. Use stream() method."
        )
