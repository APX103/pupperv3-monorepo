"""LiveKit Agent for Pupper V3 simulation control.

Sends ZMQ commands to pupperv3_sim.py instead of using ROS2.
"""

import logging

import zmq
from livekit.agents import Agent, JobContext, RunContext
from livekit.agents.llm import function_tool

from .config import (
    ANIMATION_NAMES,
    VEL_X_RANGE,
    VEL_Y_RANGE,
    VEL_YAW_RANGE,
    ZMQ_CMD_ADDR,
)

logger = logging.getLogger("pupster.sim_agent")

# Build animation descriptions for the tool
_ANIM_DESCRIPTIONS = "\n".join(
    f'- "{name}": plays the {name} animation'
    for name in ANIMATION_NAMES
)


def load_system_prompt() -> str:
    """Load system prompt."""
    prompt_path = __file__.parent / "system_prompt.md"
    if prompt_path.exists():
        return prompt_path.read_text().strip()
    return (
        "You are Pupster, a playful and loving robot dog. "
        "You live on the planet Spoon and love doing tricks. "
        "When the user asks you to do something, use your tools. "
        "Keep responses short and enthusiastic."
    )


class SimPupsterAgent(Agent):
    """Pupster agent that controls the MuJoCo simulation via ZMQ."""

    def __init__(self, zmq_pub: zmq.Socket) -> None:
        super().__init__(instructions=load_system_prompt())
        self._zmq = zmq_pub

    def _send(self, msg: dict) -> None:
        self._zmq.send_json(msg)
        logger.info(f"[ZMQ -> sim] {msg}")

    async def on_enter(self) -> None:
        logger.info("SimPupsterAgent entering")
        chat_ctx = self.chat_ctx.copy()
        chat_ctx.add_message(
            role="system",
            content="Say hi to the user and introduce yourself as Pupster.",
        )
        await self.update_chat_ctx(chat_ctx)
        self.session.generate_reply()

    @function_tool
    async def queue_animation(self, context: RunContext, animation_name: str):
        """Play a pre-recorded trick animation on the robot.

Use this when the user asks you to do a trick, such as:
'do a backflip', 'shake', 'dance', 'do the superman', 'play dead',
'swim', 'sneeze', 'do yoga', 'push up', 'twerk', etc.

Available animations:
{descriptions}

Args:
            animation_name: The name of the animation from the available list.
        """.format(descriptions=_ANIM_DESCRIPTIONS)
        if animation_name not in ANIMATION_NAMES:
            available = ", ".join(f'"{n}"' for n in ANIMATION_NAMES)
            return f"Unknown animation '{animation_name}'. Available: {available}"

        csv_stem = ANIMATION_NAMES[animation_name]
        self._send({"type": "animation", "name": csv_stem})
        return f"Playing animation: {animation_name}"

    @function_tool
    async def queue_move(
        self,
        context: RunContext,
        forward_backward_velocity: float,
        right_left_velocity: float,
        turning_velocity: float,
        duration: float,
    ):
        """Move the robot with a certain body velocity for a duration.

The robot will walk with the specified velocities and automatically stop
after the duration expires.

Args:
            forward_backward_velocity: Forward/backward speed in m/s.
                Positive = forward, negative = backward. Range [-0.75, 0.75].
                Use 0.5 for a gentle walk, 0.75 for fast.
            right_left_velocity: Left/right strafe speed in m/s.
                Positive = right, negative = left. Range [-0.5, 0.5].
            turning_velocity: Turning speed in rad/s.
                Positive = right, negative = left. Range [-2.0, 2.0].
                Use ~1.5 for a moderate turn.
            duration: How long to move in seconds. E.g. 2.0 for 2 seconds.
        """
        vx = float(forward_backward_velocity)
        vy = -float(right_left_velocity)
        wz = -float(turning_velocity)

        vx = max(VEL_X_RANGE[0], min(VEL_X_RANGE[1], vx))
        vy = max(VEL_Y_RANGE[0], min(VEL_Y_RANGE[1], vy))
        wz = max(VEL_YAW_RANGE[0], min(VEL_YAW_RANGE[1], wz))

        self._send({"type": "move", "vx": vx, "vy": vy, "wz": wz, "duration": duration})
        return f"Moving: vx={vx:.2f}, vy={vy:.2f}, wz={wz:.2f} for {duration}s"

    @function_tool
    async def immediate_stop(self, context: RunContext):
        """Immediately stop all movement and animation. Use when the user says 'stop', 'freeze', or 'halt'."""
        self._send({"type": "stop"})
        return "Stopped."

    @function_tool
    async def reset(self, context: RunContext):
        """Reset the robot to its default standing pose."""
        self._send({"type": "reset"})
        return "Reset to default pose."
