"""Text-based Pupster Agent — same logic as SimPupsterAgent, no LiveKit dependency.

Sends ZMQ commands to pupperv3_sim.py, exposes tool definitions for OpenAI function calling.
"""

import logging
from pathlib import Path

import zmq

from agent.config import (
    ANIMATION_NAMES,
    VEL_X_RANGE,
    VEL_Y_RANGE,
    VEL_YAW_RANGE,
    ZMQ_CMD_ADDR,
)

logger = logging.getLogger("pupster.text_agent")

_ANIM_DESCRIPTIONS = "\n".join(
    f'- "{name}": plays the {name} animation'
    for name in ANIMATION_NAMES
)


def load_system_prompt() -> str:
    prompt_path = Path(__file__).resolve().parent.parent / "agent" / "system_prompt.md"
    if prompt_path.exists():
        return prompt_path.read_text().strip()
    return (
        "You are Pupster, a playful and loving robot dog. "
        "You live on the planet Spoon and love doing tricks. "
        "When the user asks you to do something, use your tools. "
        "Keep responses short and enthusiastic."
    )


class TextPupsterAgent:
    """Text-only agent with the same tool logic as SimPupsterAgent."""

    def __init__(self) -> None:
        ctx = zmq.Context()
        self._zmq = ctx.socket(zmq.PUB)
        self._zmq.bind(ZMQ_CMD_ADDR)
        logger.info(f"ZMQ publisher bound to {ZMQ_CMD_ADDR}")

    def _send(self, msg: dict) -> str:
        self._zmq.send_json(msg)
        logger.info(f"[ZMQ -> sim] {msg}")
        return str(msg)

    # --- Tool implementations (same logic as SimPupsterAgent) ---

    def queue_animation(self, animation_name: str) -> str:
        if animation_name not in ANIMATION_NAMES:
            available = ", ".join(f'"{n}"' for n in ANIMATION_NAMES)
            return f"Unknown animation '{animation_name}'. Available: {available}"

        csv_stem = ANIMATION_NAMES[animation_name]
        self._send({"type": "animation", "name": csv_stem})
        return f"Playing animation: {animation_name}"

    def queue_move(self, forward_backward_velocity: float, right_left_velocity: float, turning_velocity: float, duration: float) -> str:
        vx = float(forward_backward_velocity)
        vy = -float(right_left_velocity)
        wz = -float(turning_velocity)

        vx = max(VEL_X_RANGE[0], min(VEL_X_RANGE[1], vx))
        vy = max(VEL_Y_RANGE[0], min(VEL_Y_RANGE[1], vy))
        wz = max(VEL_YAW_RANGE[0], min(VEL_YAW_RANGE[1], wz))

        self._send({"type": "move", "vx": vx, "vy": vy, "wz": wz, "duration": duration})
        return f"Moving: vx={vx:.2f}, vy={vy:.2f}, wz={wz:.2f} for {duration}s"

    def immediate_stop(self) -> str:
        self._send({"type": "stop"})
        return "Stopped."

    def reset(self) -> str:
        self._send({"type": "reset"})
        return "Reset to default pose."

    # --- Tool dispatch ---

    _TOOL_MAP = {
        "queue_animation": queue_animation,
        "queue_move": queue_move,
        "immediate_stop": immediate_stop,
        "reset": reset,
    }

    def call_tool(self, name: str, arguments: dict) -> str:
        fn = self._TOOL_MAP.get(name)
        if fn is None:
            return f"Unknown tool: {name}"
        return fn(self, **arguments)

    # --- OpenAI function calling tool definitions ---

    @property
    def tools(self) -> list[dict]:
        return [
            {
                "type": "function",
                "function": {
                    "name": "queue_animation",
                    "description": (
                        "Play a pre-recorded trick animation on the robot.\n"
                        "Use when the user asks to do a trick: backflip, shake, dance, "
                        "superman, play dead, swim, sneeze, yoga, push up, twerk, etc.\n\n"
                        f"Available animations:\n{_ANIM_DESCRIPTIONS}"
                    ),
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "animation_name": {
                                "type": "string",
                                "description": "The name of the animation from the available list.",
                                "enum": list(ANIMATION_NAMES),
                            },
                        },
                        "required": ["animation_name"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "queue_move",
                    "description": (
                        "Move the robot with body velocity for a duration. "
                        "Automatically stops after duration expires."
                    ),
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "forward_backward_velocity": {
                                "type": "number",
                                "description": "Forward/backward speed in m/s. Positive=forward. Range [-0.75, 0.75]. Use 0.5 for walk, 0.75 for fast.",
                            },
                            "right_left_velocity": {
                                "type": "number",
                                "description": "Left/right strafe speed in m/s. Positive=right. Range [-0.5, 0.5].",
                            },
                            "turning_velocity": {
                                "type": "number",
                                "description": "Turning speed in rad/s. Positive=right. Range [-2.0, 2.0]. Use ~1.5 for moderate turn.",
                            },
                            "duration": {
                                "type": "number",
                                "description": "How long to move in seconds.",
                            },
                        },
                        "required": ["forward_backward_velocity", "right_left_velocity", "turning_velocity", "duration"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "immediate_stop",
                    "description": "Immediately stop all movement and animation. Use when user says 'stop', 'freeze', or 'halt'.",
                    "parameters": {"type": "object", "properties": {}, "required": []},
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "reset",
                    "description": "Reset the robot to its default standing pose.",
                    "parameters": {"type": "object", "properties": {}, "required": []},
                },
            },
        ]
