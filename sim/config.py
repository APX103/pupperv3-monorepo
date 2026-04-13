"""Constants from ROS2 config and training environment."""

# Joint names in policy order
JOINT_NAMES = [
    "leg_front_r_1", "leg_front_r_2", "leg_front_r_3",
    "leg_front_l_1", "leg_front_l_2", "leg_front_l_3",
    "leg_back_r_1",  "leg_back_r_2",  "leg_back_r_3",
    "leg_back_l_1",  "leg_back_l_2",  "leg_back_l_3",
]

NUM_JOINTS = 12

# Default standing pose (from training config.yaml)
DEFAULT_JOINT_POS = [0.26, 0.0, -0.52, -0.26, 0.0, 0.52, 0.26, 0.0, -0.52, -0.26, 0.0, 0.52]

# Single observation = 36 dims: ang_vel(3) + gravity(3) + cmd(3) + orientation(3) + joint_pos(12) + last_action(12)
SINGLE_OBS_SIZE = 36

# Observation history (overridden by policy JSON)
OBSERVATION_HISTORY_DEFAULT = 4

# Action scale (overridden by policy JSON)
ACTION_SCALE_DEFAULT = 0.75

# PD gains (built into training XML actuators: gainprm="5.0 0 0" biasprm="0 -5.0 -0.1")
KP = 5.0
KD = 0.1

# Velocity command limits (from training)
VEL_X_RANGE = (-0.75, 0.75)
VEL_Y_RANGE = (-0.5, 0.5)
VEL_YAW_RANGE = (-2.0, 2.0)

# Physics timestep (from training XML: timestep="0.004")
PHYSICS_DT = 0.004
POLICY_HZ = 50  # 50Hz policy inference
PHYSICS_STEPS_PER_POLICY = 5  # 0.02s / 0.004s

# Observation clip
OBSERVATION_LIMIT = 100.0

# Path to training XML (relative to repo root)
MODEL_XML = "ros2_ws/src/pupper_v3_description/description/mujoco_xml/pupper_v3_complete.mjx.position.xml"
