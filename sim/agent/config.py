"""Agent configuration: animation names, ZMQ address, model paths."""

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
ANIMATIONS_DIR = REPO_ROOT / "ros2_ws/src/animation_controller_py/launch/animations"

# ZMQ command socket address (must match pupperv3_sim.py)
ZMQ_CMD_ADDR = "ipc:///tmp/pupper_sim_cmd"

# Animation name -> CSV stem mapping
ANIMATION_NAMES = {
    "twerk": "twerk_recording_2025-09-04_16-14-51_0",
    "lie_sit_lie": "lie_sit_lie_recording_2025-09-03_12-44-08_0",
    "sit_shake": "stand_sit_shake_sit_stand_recording_2025-09-03_12-47-18_0",
    "sit_stand": "stand_sit_stand_recording_2025-09-03_12-46-36_0",
    "upward_dog": "upward_dog_recording_2025-10-22_17-17-07",
    "superman": "superman_recording_2025-10-22_17-47-41",
    "pee": "pee2_recording_2025-10-22_17-41-45",
    "downward_dog": "lie_downward_dog_recording_2025-09-04_16-08-00_0",
    "stand_downward_dog": "stand_downward_dog_recording_2025-09-04_16-09-51_0",
    "spider": "spider_recording_2025-09-04_16-12-38_0",
    "swim": "swim_recording_2025-09-04_16-10-45_0",
    "sneeze": "sneeze_recording_2025-09-04_16-13-54_0",
    "push_up": "push_up_recording_2025-09-04_16-11-34_0",
}

# Velocity limits (must match sim/config.py)
VEL_X_RANGE = (-0.75, 0.75)
VEL_Y_RANGE = (-0.5, 0.5)
VEL_YAW_RANGE = (-2.0, 2.0)

# LiveKit server config (loaded from env or defaults)
LIVEKIT_URL = "ws://localhost:7880"
LIVEKIT_API_KEY = "pupster"
LIVEKIT_API_SECRET = "dev-secret-123"
