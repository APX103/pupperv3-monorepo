"""Piper TTS plugin for LiveKit Agents.

Local, offline text-to-speech using Piper. CPU-only, ~10ms latency.

Usage:
    tts = PiperTTS(voice_path="en_US-lessac-medium.onnx")
    session = AgentSession(tts=tts, ...)

Models:
    Download from https://huggingface.co/rhasspy/piper-voices
    - English: en_US-lessac-medium.onnx (natural, neutral voice)
    - Chinese: zh_CN-huayan-medium.onnx
"""

import json
import logging
from pathlib import Path

logger = logging.getLogger("pupster.tts")

try:
    import numpy as np
except ImportError:
    np = None  # type: ignore


def _require_deps():
    from livekit.agents import tts as _tts
    if np is None:
        raise ImportError("numpy is required. Install with: pip install numpy")
    return _tts


class PiperTTSSynthesizeStream:
    """Stream that synthesizes text using Piper and yields audio frames."""

    def __init__(self, tts_impl, text: str):
        from livekit.agents import tts
        self._tts_impl = tts_impl
        self._text = text
        self._stream = tts.ChunkedStream(tts_impl)

    @property
    def _event_ch(self):
        return self._stream._event_ch

    async def _run(self):
        from livekit.agents import tts

        voice = self._tts_impl._voice
        for chunk in voice.synthesize(self._text):
            # audio_int16_bytes gives us PCM16 ready for LiveKit
            audio_data = chunk.audio_int16_bytes
            frame_size = int(self._tts_impl.sample_rate * 0.02)  # 20ms chunks
            frame_bytes = frame_size * 2  # 16-bit = 2 bytes per sample
            for i in range(0, len(audio_data), frame_bytes):
                piece = audio_data[i:i + frame_bytes]
                if len(piece) == 0:
                    break
                frame = tts.SynthesisFrame(
                    data=piece,
                    sample_rate=self._tts_impl.sample_rate,
                    num_channels=1,
                )
                self._event_ch.send(frame)


class PiperTTS:
    """Local Piper TTS implementation compatible with LiveKit Agents."""

    def __init__(
        self,
        voice_path: str | Path,
        num_channels: int = 1,
    ):
        self._tts_module = _require_deps()

        voice_path = Path(voice_path)
        if not voice_path.exists():
            raise FileNotFoundError(f"Voice model not found: {voice_path}")

        self._voice_path = voice_path
        self.num_channels = num_channels
        self._voice = None

        import piper
        import onnxruntime as ort
        self._piper = piper
        self._ort = ort

        logger.info(f"Loading Piper voice: {voice_path.name}")
        self._load_voice()

    def _load_voice(self):
        config_path = self._voice_path.with_suffix(".onnx.json")
        if not config_path.exists():
            raise FileNotFoundError(
                f"Piper config not found: {config_path}\n"
                "Download alongside the .onnx file from HuggingFace."
            )

        with open(config_path) as f:
            config_data = json.load(f)
        config = self._piper.config.PiperConfig.from_dict(config_data)
        session = self._ort.InferenceSession(str(self._voice_path))
        self._voice = self._piper.PiperVoice(session, config)
        self.sample_rate = config.sample_rate
        logger.info(f"Piper voice loaded. Sample rate: {self.sample_rate}Hz")

    def synthesize(self, text: str, *, conn_options=None):
        return PiperTTSSynthesizeStream(self, text)

    def stream(self, *, conn_options=None):
        return self._tts_module.ChunkedStream(self)

    @property
    def model(self) -> str:
        return self._voice_path.stem

    @property
    def provider(self) -> str:
        return "piper-local"
