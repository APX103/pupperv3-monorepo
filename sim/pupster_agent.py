"""Standalone Pupster Agent — connects to self-hosted LiveKit Server
and controls the MuJoCo simulation via ZMQ commands.

Supports both local (Sherpa-ONNX + Piper) and cloud (Deepgram + Cartesia) STT/TTS.

Usage:
    # With local STT/TTS
    uv run python puppster_agent.py \
        --stt-model /path/to/sherpa-onnx-streaming-zipformer-bilingual-zh-en-2023-02-20 \
        --tts-voice /path/to/en_US-lessac-medium.onnx

    # With cloud STT/TTS (default)
    uv run python puppster_agent.py
"""

import argparse
import logging
import os

import zmq
from dotenv import load_dotenv
from livekit import api
from livekit.agents import AgentSession, WorkerOptions, cli

from agent.agent import SimPupsterAgent
from agent.config import ZMQ_CMD_ADDR

logger = logging.getLogger("pupster.agent")

# Load environment variables
load_dotenv(".env.local")
load_dotenv()


def prewarm(proc: api.JobProcess):
    proc.session.state = api.JobProcessState.JOB_PROCESS_STATE_RUNNING


def create_session(
    stt_provider: str,
    stt_model: str | None,
    tts_provider: str,
    tts_voice: str | None,
    llm_provider: str,
    llm_model: str,
) -> AgentSession:
    """Create AgentSession with the specified STT/TTS/LLM providers."""

    # --- STT ---
    if stt_provider == "local":
        from agent.voices.stt import SherpaOnnxSTT
        logger.info(f"Using local STT: Sherpa-ONNX ({stt_model})")
        stt_impl = SherpaOnnxSTT(model_dir=stt_model)
    elif stt_provider == "deepgram":
        from livekit.plugins import deepgram
        logger.info("Using cloud STT: Deepgram")
        stt_impl = deepgram.STT(model="nova-3", language="multi")
    else:
        raise ValueError(f"Unknown STT provider: {stt_provider}")

    # --- TTS ---
    if tts_provider == "local":
        from agent.voices.tts import PiperTTS
        logger.info(f"Using local TTS: Piper ({tts_voice})")
        tts_impl = PiperTTS(voice_path=tts_voice)
    elif tts_provider == "cartesia":
        from livekit.plugins import cartesia
        logger.info("Using cloud TTS: Cartesia")
        tts_impl = cartesia.TTS(
            voice="e7651bee-f073-4b79-9156-eff1f8ae4fd9",
            model="sonic-2",
        )
    else:
        raise ValueError(f"Unknown TTS provider: {tts_provider}")

    # --- LLM ---
    from livekit.plugins import openai
    if llm_provider == "glm":
        base_url = os.getenv("GLM_BASE_URL", "https://open.bigmodel.cn/api/coding/paas/v4")
        api_key = os.getenv("GLM_API_KEY")
        if not api_key:
            raise ValueError("GLM_API_KEY env var is required for --llm-provider glm")
        logger.info(f"Using cloud LLM: GLM ({llm_model}, {base_url})")
        llm_impl = openai.LLM(model=llm_model, api_key=api_key, base_url=base_url)
    else:
        api_key = os.getenv("OPENAI_API_KEY")
        logger.info(f"Using cloud LLM: OpenAI ({llm_model})")
        llm_impl = openai.LLM(model=llm_model, api_key=api_key)

    # --- VAD + Turn Detection ---
    from livekit.plugins import silero
    vad_impl = silero.VAD.load()

    return AgentSession(
        stt=stt_impl,
        llm=llm_impl,
        tts=tts_impl,
        vad=vad_impl,
    )


async def entrypoint(job: api.Job):
    """Main entrypoint — called when a LiveKit job is assigned."""
    # Parse arguments (stored in metadata by CLI)
    args = argparse.Namespace(**job.metadata)

    logger.info("Starting SimPupsterAgent")
    logger.info(f"  STT: {args.stt_provider} ({args.stt_model})")
    logger.info(f"  TTS: {args.tts_provider} ({args.tts_voice})")
    logger.info(f"  LLM: {args.llm_provider} ({args.llm_model})")

    # Connect to LiveKit server
    livekit_url = os.getenv("LIVEKIT_URL", "ws://localhost:7880")
    livekit_api_key = os.getenv("LIVEKIT_API_KEY", "pupster")
    livekit_api_secret = os.getenv("LIVEKIT_API_SECRET", "dev-secret-123")

    logger.info(f"Connecting to LiveKit at {livekit_url}")

    # Set up ZMQ publisher to send commands to simulation
    zmq_ctx = zmq.Context()
    zmq_pub = zmq_ctx.socket(zmq.PUB)
    zmq_pub.bind(ZMQ_CMD_ADDR)
    logger.info(f"ZMQ publisher bound to {ZMQ_CMD_ADDR}")

    # Create session with configured providers
    session = create_session(
        stt_provider=args.stt_provider,
        stt_model=args.stt_model,
        tts_provider=args.tts_provider,
        tts_voice=args.tts_voice,
        llm_provider=args.llm_provider,
        llm_model=args.llm_model,
    )

    agent = SimPupsterAgent(zmq_pub)
    await session.connect(job)
    await session.start(agent)

    logger.info("Agent session ended")


def main():
    parser = argparse.ArgumentParser(description="Pupster Sim Agent — voice control for MuJoCo simulation")
    parser.add_argument(
        "--stt-provider",
        choices=["local", "deepgram"],
        default=os.getenv("STT_PROVIDER", "deepgram"),
        help="STT provider: local (Sherpa-ONNX) or deepgram (cloud)",
    )
    parser.add_argument(
        "--stt-model",
        default=os.getenv("STT_MODEL", ""),
        help="Path to Sherpa-ONNX model directory (required for --stt-provider local)",
    )
    parser.add_argument(
        "--tts-provider",
        choices=["local", "cartesia"],
        default=os.getenv("TTS_PROVIDER", "cartesia"),
        help="TTS provider: local (Piper) or cartesia (cloud)",
    )
    parser.add_argument(
        "--tts-voice",
        default=os.getenv("TTS_VOICE", ""),
        help="Path to Piper .onnx voice file (required for --tts-provider local)",
    )
    parser.add_argument(
        "--llm-provider",
        choices=["openai", "glm"],
        default=os.getenv("LLM_PROVIDER", "glm"),
        help="LLM provider: openai or glm (GLM Coding Plan)",
    )
    parser.add_argument(
        "--llm-model",
        default=os.getenv("LLM_MODEL", "glm-5-turbo"),
        help="LLM model name",
    )

    args = parser.parse_args()

    # Validate required paths
    if args.stt_provider == "local" and not args.stt_model:
        parser.error("--stt-model is required when using --stt-provider local")
    if args.tts_provider == "local" and not args.tts_voice:
        parser.error("--tts-voice is required when using --tts-provider local")

    # Store args in metadata for access in entrypoint
    worker_options = WorkerOptions(
        prewarm_fnc=prewarm,
        metadata=vars(args),
    )

    cli.run_app(entrypoint, worker_options=worker_options)


if __name__ == "__main__":
    main()
