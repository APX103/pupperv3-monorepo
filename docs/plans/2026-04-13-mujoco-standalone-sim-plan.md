# Standalone MuJoCo Simulation Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Create a standalone MuJoCo simulation that runs the trained Pupper V3 locomotion policy with keyboard control, independent of ROS2.

**Architecture:** Uses the training XML (`pupper_v3_complete.mjx.position.xml`) so MuJoCo's built-in actuator PD (kp=5.0, kd=0.1) matches training. NumPy-only policy inference loads RTNeural JSON format. 50Hz policy loop with 5× 0.004s physics steps. Keyboard maps to velocity commands.

**Tech Stack:** Python, mujoco, numpy, uv

**Design doc:** `docs/plans/2026-04-13-mujoco-standalone-sim-design.md`

**Key reference files:**
- Training XML: `ros2_ws/src/pupper_v3_description/description/mujoco_xml/pupper_v3_complete.mjx.position.xml`
- Policy JSON (LFS): `ros2_ws/src/neural_controller/launch/policy_latest.json`
- ROS2 config: `ros2_ws/src/neural_controller/launch/config.yaml`
- Neural controller C++ (observation logic): `ros2_ws/src/neural_controller/src/neural_controller.cpp:450-610`

---

### Task 1: Set up uv project

**Files:**
- Create: `sim/pyproject.toml`

**Step 1: Create the sim directory and pyproject.toml**

```toml
[project]
name = "pupperv3-sim"
version = "0.1.0"
requires-python = ">=3.11"
dependencies = [
    "mujoco>=2.3.0",
    "numpy>=1.24",
]

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"
```

**Step 2: Initialize uv environment**

Run: `cd sim && uv sync`
Expected: Creates `.venv/` with mujoco and numpy installed.

**Step 3: Commit**

```bash
git add sim/pyproject.toml sim/uv.lock
git commit -m "feat(sim): initialize uv project with mujoco and numpy"
```

---

### Task 2: Create config.py

**Files:**
- Create: `sim/config.py`

**Step 1: Write constants**

Extract from ROS2 `config.yaml` and training config. These are fallback defaults — the real values come from the policy JSON at runtime.

```python
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
```

**Step 2: Commit**

```bash
git add sim/config.py
git commit -m "feat(sim): add config constants from training and ROS2"
```

---

### Task 3: Create policy.py with tests

**Files:**
- Create: `sim/policy.py`
- Create: `sim/test_policy.py`

**Step 1: Write the failing test**

Create a minimal synthetic RTNeural JSON for testing:

```python
"""Tests for policy loading and inference."""

import json
import numpy as np
import pytest
from policy import RTNeuralPolicy


def _make_tiny_json(obs_size=12, act_size=3, history=1):
    """Create a minimal RTNeural JSON: one hidden layer, ELU, output tanh."""
    hidden = 4
    return json.dumps({
        "in_shape": [1, obs_size * history],
        "layers": [
            {
                "type": "dense",
                "activation": "elu",
                "shape": [hidden],
                "weights": [
                    [[float(i * hidden + j) for j in range(obs_size * history)] for i in range(hidden)],
                    [0.0] * hidden,
                ],
            },
            {
                "type": "dense",
                "activation": "tanh",
                "shape": [act_size],
                "weights": [
                    [[float(i * hidden + j) for j in range(hidden)] for i in range(act_size)],
                    [0.0] * act_size,
                ],
            },
        ],
        "observation_history": history,
        "action_scale": 0.5,
        "default_joint_pos": [0.1, 0.2, 0.3],
        "kp": 5.0,
        "kd": 0.1,
    })


def test_load_policy(tmp_path):
    p = tmp_path / "test_policy.json"
    p.write_text(_make_tiny_json())

    policy = RTNeuralPolicy(str(p))
    assert policy.input_size == 12
    assert policy.output_size == 3
    assert policy.observation_history == 1
    assert policy.action_scale == 0.5
    assert list(policy.default_joint_pos) == [0.1, 0.2, 0.3]


def test_forward_shape(tmp_path):
    p = tmp_path / "test_policy.json"
    p.write_text(_make_tiny_json(obs_size=12, act_size=3))

    policy = RTNeuralPolicy(str(p))
    obs = np.zeros(12, dtype=np.float32)
    output = policy.forward(obs)
    assert output.shape == (3,)


def test_forward_deterministic(tmp_path):
    p = tmp_path / "test_policy.json"
    p.write_text(_make_tiny_json())

    policy = RTNeuralPolicy(str(p))
    obs = np.ones(12, dtype=np.float32)
    out1 = policy.forward(obs)
    out2 = policy.forward(obs)
    np.testing.assert_array_equal(out1, out2)


def test_forward_output_range(tmp_path):
    """Tanh output should be in [-1, 1]."""
    p = tmp_path / "test_policy.json"
    p.write_text(_make_tiny_json(obs_size=12, act_size=3))

    policy = RTNeuralPolicy(str(p))
    obs = np.random.randn(12).astype(np.float32) * 10
    output = policy.forward(obs)
    assert np.all(output >= -1.0) and np.all(output <= 1.0)


def test_observation_history_size(tmp_path):
    p = tmp_path / "test_policy.json"
    p.write_text(_make_tiny_json(obs_size=6, act_size=2, history=3))

    policy = RTNeuralPolicy(str(p))
    assert policy.input_size == 18  # 6 * 3
    assert policy.observation_history == 3
```

**Step 2: Run tests to verify they fail**

Run: `cd sim && uv run pytest test_policy.py -v`
Expected: FAIL (ModuleNotFoundError: No module named 'policy')

**Step 3: Write policy.py**

```python
"""RTNeural JSON policy loader with NumPy forward pass."""

import json
from dataclasses import dataclass

import numpy as np


def _elu(x: np.ndarray) -> np.ndarray:
    return np.where(x > 0, x, np.exp(x) - 1)


@dataclass
class DenseLayer:
    weight: np.ndarray  # shape: (in_features, out_features)
    bias: np.ndarray    # shape: (out_features,)
    activation: str     # "elu", "tanh", or ""

    def __call__(self, x: np.ndarray) -> np.ndarray:
        out = x @ self.weight + self.bias
        if self.activation == "elu":
            return _elu(out)
        elif self.activation == "tanh":
            return np.tanh(out)
        return out


class RTNeuralPolicy:
    """Load an RTNeural-format JSON policy and run inference with NumPy."""

    def __init__(self, json_path: str):
        with open(json_path, "r") as f:
            data = json.load(f)

        self.input_size = data["in_shape"][1]
        self.output_size = data["layers"][-1]["shape"][0]
        self.observation_history = data.get("observation_history", 1)
        self.action_scale = data.get("action_scale", 0.75)
        self.default_joint_pos = np.array(
            data.get("default_joint_pos", [0.0] * self.output_size), dtype=np.float32
        )

        # Build layer stack
        self.layers: list[DenseLayer] = []
        for layer_data in data["layers"]:
            if layer_data["type"] != "dense":
                raise ValueError(f"Unsupported layer type: {layer_data['type']}")
            weights = np.array(layer_data["weights"][0], dtype=np.float32)
            bias = np.array(layer_data["weights"][1], dtype=np.float32)
            self.layers.append(DenseLayer(
                weight=weights,
                bias=bias,
                activation=layer_data.get("activation", ""),
            ))

    def forward(self, observation: np.ndarray) -> np.ndarray:
        """Run forward pass. Returns tanh-clipped action vector."""
        x = observation.astype(np.float32)
        for layer in self.layers:
            x = layer(x)
        return x
```

**Step 4: Run tests to verify they pass**

Run: `cd sim && uv run pytest test_policy.py -v`
Expected: All 5 tests PASS

**Step 5: Commit**

```bash
git add sim/policy.py sim/test_policy.py
git commit -m "feat(sim): add RTNeural JSON policy loader with NumPy inference"
```

---

### Task 4: Create observations.py with tests

**Files:**
- Create: `sim/observations.py`
- Create: `sim/test_observations.py`

**Context from C++ source** (`neural_controller.cpp:452-480`):
- Angular velocity: directly from gyro sensor (3 dims)
- Projected gravity: `R_body_to_world^{-1} × (0, 0, -1)` where R is from quaternion (w,x,y,z) (3 dims)
- Velocity commands: from user input (3 dims)
- Desired body orientation: world z-axis in body frame, default = (0, 0, 1) when no pitch/roll command (3 dims)
- Joint positions: `q - default_pos` for each joint (12 dims)
- Last action: previous policy output (12 dims)

After each inference, observation history is rotated RIGHT by 36 slots:
`std::rotate(observation_.rbegin(), observation_.rbegin() + kSingleObservationSize, observation_.rend())`
This moves the oldest chunk to the end and shifts everything right, then slot [0:36] is overwritten with new data.

**Step 1: Write the failing test**

```python
"""Tests for observation construction."""

import numpy as np
from observations import ObservationBuilder


def test_single_obs_size():
    builder = ObservationBuilder(history=1, default_pos=np.zeros(12))
    assert builder.total_size == 36
    assert builder.buffer.shape == (36,)


def test_history_size():
    builder = ObservationBuilder(history=4, default_pos=np.zeros(12))
    assert builder.total_size == 144
    assert builder.buffer.shape == (144,)


def test_build_and_shift():
    builder = ObservationBuilder(history=2, default_pos=np.zeros(12))
    ang_vel = np.array([1.0, 2.0, 3.0])
    quat = np.array([1.0, 0.0, 0.0, 0.0])  # identity → gravity in body = (0, 0, -1)
    cmd_vel = np.array([0.5, 0.0, 0.0])
    joint_pos = np.ones(12)
    last_action = np.zeros(12)

    obs1 = builder.build(ang_vel, quat, cmd_vel, joint_pos, last_action)

    # First 3 = ang_vel
    np.testing.assert_array_almost_equal(obs1[:3], [1.0, 2.0, 3.0])
    # Gravity projection: identity quat, R^{-1} × (0,0,-1) = (0, 0, -1)
    np.testing.assert_array_almost_equal(obs1[3:6], [0.0, 0.0, -1.0])
    # cmd_vel
    np.testing.assert_array_almost_equal(obs1[6:9], [0.5, 0.0, 0.0])
    # Desired orientation: world z in body frame, identity → (0, 0, 1)
    np.testing.assert_array_almost_equal(obs1[9:12], [0.0, 0.0, 1.0])
    # Joint pos - default (zeros)
    np.testing.assert_array_almost_equal(obs1[12:24], np.ones(12))
    # Last action
    np.testing.assert_array_almost_equal(obs1[24:36], np.zeros(12))

    # Second call: old obs should be shifted to slots [36:72]
    obs2 = builder.build(ang_vel * 2, quat, cmd_vel, joint_pos * 2, last_action)
    # First chunk: new data
    np.testing.assert_array_almost_equal(obs2[:3], [2.0, 4.0, 6.0])
    # Second chunk: previous observation
    np.testing.assert_array_almost_equal(obs2[36:39], [1.0, 2.0, 3.0])


def test_observation_clipped():
    builder = ObservationBuilder(history=1, default_pos=np.zeros(12), clip=10.0)
    ang_vel = np.array([1000.0, 0.0, 0.0])  # way over clip limit
    obs = builder.build(ang_vel, np.array([1.0, 0.0, 0.0, 0.0]),
                         np.zeros(3), np.zeros(12), np.zeros(12))
    assert obs[0] == 10.0


def test_joint_pos_normalized():
    builder = ObservationBuilder(
        history=1,
        default_pos=np.array([0.26, 0.0, -0.52, -0.26, 0.0, 0.52,
                              0.26, 0.0, -0.52, -0.26, 0.0, 0.52], dtype=np.float32),
    )
    joint_pos = np.array([0.26, 0.0, -0.52, -0.26, 0.0, 0.52,
                          0.26, 0.0, -0.52, -0.26, 0.0, 0.52], dtype=np.float32)
    obs = builder.build(np.zeros(3), np.array([1.0, 0.0, 0.0, 0.0]),
                         np.zeros(3), joint_pos, np.zeros(12))
    # Joint positions should be zero when at default
    np.testing.assert_array_almost_equal(obs[12:24], np.zeros(12))
```

**Step 2: Run tests to verify they fail**

Run: `cd sim && uv run pytest test_observations.py -v`
Expected: FAIL

**Step 3: Write observations.py**

```python
"""Observation builder matching the C++ neural controller logic."""

import numpy as np
from config import SINGLE_OBS_SIZE


def _quat_to_rotation_matrix(w: float, x: float, y: float, z: float) -> np.ndarray:
    """Convert quaternion (w,x,y,z) to 3x3 rotation matrix."""
    # R_body_to_world
    R = np.array([
        [1 - 2*(y*y + z*z),  2*(x*y - w*z),      2*(x*z + w*y)],
        [2*(x*y + w*z),      1 - 2*(x*x + z*z),  2*(y*z - w*x)],
        [2*(x*z - w*y),      2*(y*z + w*x),      1 - 2*(x*x + y*y)],
    ], dtype=np.float64)
    return R


class ObservationBuilder:
    """Build the observation vector with history, matching neural_controller.cpp."""

    def __init__(self, history: int, default_pos: np.ndarray, clip: float = 100.0):
        self.history = history
        self.default_pos = default_pos.astype(np.float32)
        self.clip = clip
        self.total_size = SINGLE_OBS_SIZE * history
        self.buffer = np.zeros(self.total_size, dtype=np.float32)

    def build(self, ang_vel: np.ndarray, quat: np.ndarray,
              cmd_vel: np.ndarray, joint_pos: np.ndarray,
              last_action: np.ndarray) -> np.ndarray:
        """Build observation, shift history, return full buffer."""
        # Shift history right by SINGLE_OBS_SIZE
        # Equivalent to C++: std::rotate(rbegin, rbegin + kSingleObsSize, rend)
        self.buffer[SINGLE_OBS_SIZE:] = self.buffer[:-SINGLE_OBS_SIZE]

        # Angular velocity [0:3]
        self.buffer[0:3] = ang_vel[:3]

        # Projected gravity [3:6]: R_body_to_world^{-1} × (0, 0, -1)
        w, x, y, z = quat[0], quat[1], quat[2], quat[3]
        R = _quat_to_rotation_matrix(w, x, y, z)
        gravity_world = np.array([0.0, 0.0, -1.0], dtype=np.float64)
        gravity_body = R.T @ gravity_world  # R^{-1} = R^T for orthogonal matrix
        self.buffer[3:6] = gravity_body.astype(np.float32)

        # Velocity commands [6:9]
        self.buffer[6:9] = cmd_vel[:3]

        # Desired body orientation [9:12]: world z in body frame = R^T @ (0,0,1)
        # Default (no pitch/roll command) = (0, 0, 1)
        self.buffer[9:12] = np.array([0.0, 0.0, 1.0], dtype=np.float32)

        # Joint positions [12:24]: q - default_pos
        self.buffer[12:24] = (joint_pos[:12] - self.default_pos).astype(np.float32)

        # Last action [24:36]
        self.buffer[24:36] = last_action[:12].astype(np.float32)

        # Clip
        np.clip(self.buffer, -self.clip, self.clip, out=self.buffer)

        return self.buffer.copy()
```

**Step 4: Run tests to verify they pass**

Run: `cd sim && uv run pytest test_observations.py -v`
Expected: All 4 tests PASS

**Step 5: Commit**

```bash
git add sim/observations.py sim/test_observations.py
git commit -m "feat(sim): add observation builder matching C++ neural controller"
```

---

### Task 5: Create main simulation script

**Files:**
- Create: `sim/pupperv3_sim.py`

This is the integration of all components. No unit test — run it and verify the robot stands/walks.

**Step 1: Write pupperv3_sim.py**

Key implementation details:
- Load training XML (not ROS2 XML) so MuJoCo's built-in PD matches training
- `mujoco.viewer.launch_passive()` for rendering
- Register keyboard callback via `viewer.user_key_callback`
- Set `data.ctrl[:]` = target joint position (action_scale × policy_output + default_pos)
- Run 5 `mj_step` per policy inference (50Hz policy, 0.004s physics)
- Read sensors: `data.sensor("body_gyro").data` for ang_vel, `data.sensor("body_quat").data` for quaternion
- Read joint positions from `data.qpos[joint_offset:]` where offset accounts for freejoint (7 DOF)
- Find joint qpos indices from `model.jnt_qposadr`

```python
"""Standalone MuJoCo simulation for Pupper V3 with keyboard control."""

import sys
from pathlib import Path

import mujoco
import mujoco.viewer
import numpy as np

from config import (
    ACTION_SCALE_DEFAULT,
    DEFAULT_JOINT_POS,
    MODEL_XML,
    NUM_JOINTS,
    OBSERVATION_LIMIT,
    OBSERVATION_HISTORY_DEFAULT,
    PHYSICS_DT,
    PHYSICS_STEPS_PER_POLICY,
    SINGLE_OBS_SIZE,
    VEL_X_RANGE,
    VEL_Y_RANGE,
    VEL_YAW_RANGE,
)
from observations import ObservationBuilder
from policy import RTNeuralPolicy

REPO_ROOT = Path(__file__).resolve().parent.parent


def main():
    policy_path = sys.argv[1] if len(sys.argv) > 1 else None
    xml_path = REPO_ROOT / MODEL_XML

    # Load model
    model = mujoco.MjModel.from_xml_path(str(xml_path))
    model.opt.timestep = PHYSICS_DT
    data = mujoco.MjData(model)

    # Load policy
    if policy_path:
        policy = RTNeuralPolicy(policy_path)
    else:
        print("Warning: No policy JSON provided. Running with zero actions.")
        print("Usage: python pupperv3_sim.py <policy.json>")
        policy = None

    # Resolve parameters from policy JSON or defaults
    default_pos = policy.default_joint_pos if policy else np.array(DEFAULT_JOINT_POS, dtype=np.float32)
    action_scale = policy.action_scale if policy else ACTION_SCALE_DEFAULT
    history = policy.observation_history if policy else OBSERVATION_HISTORY_DEFAULT

    # Joint qpos addresses (skip freejoint 7-DOF)
    joint_qpos_adr = [model.jnt_qposadr[i] for i in range(model.njnt) if model.jnt_type[i] == mujoco.mjtJoint.mjJNT_HINGE]
    assert len(joint_qpos_adr) == NUM_JOINTS, f"Expected {NUM_JOINTS} hinge joints, got {len(joint_qpos_adr)}"

    # Observation builder
    obs_builder = ObservationBuilder(history=history, default_pos=default_pos, clip=OBSERVATION_LIMIT)

    # Velocity command state
    cmd_vel = np.array([0.0, 0.0, 0.0], dtype=np.float32)
    last_action = np.zeros(NUM_JOINTS, dtype=np.float32)

    # Initialize robot to default pose
    mujoco.mj_resetData(model, data)
    for i, adr in enumerate(joint_qpos_adr):
        data.qpos[adr] = default_pos[i]
    mujoco.mj_forward(model, data)

    # Key callback state
    key_state = {"pressed": set()}

    def key_callback(keycode):
        key_state["pressed"].add(keycode)

    def key_release_callback(keycode):
        key_state["pressed"].discard(keycode)

    # Map keycodes to velocity increments
    KEY_STEP = 0.05

    def update_cmd_vel():
        """Update cmd_vel based on currently held keys."""
        keys = key_state["pressed"]
        # Arrow keys (non-toggle: only modify while held)
        # We use a simpler approach: apply step on press, handled below in loop

    # Launch viewer
    with mujoco.viewer.launch_passive(model, data, key_callback=key_callback) as viewer:
        # Set viewer options
        viewer.opt.flags[mujoco.mjtVisFlag.mjVIS_CONTACTPOINT] = True
        viewer.cam.distance = 1.0

        step_count = 0

        while viewer.is_running():
            # Handle keyboard input
            keys = key_state["pressed"]

            # Toggle keys (press once to change)
            # Arrow keys modify velocity incrementally on each loop iteration while held
            # But we only want step-on-press behavior, so clear keys after processing

            if mujoco.mj.KEY_UP in keys:
                cmd_vel[0] = min(cmd_vel[0] + KEY_STEP, VEL_X_RANGE[1])
                key_state["pressed"].discard(mujoco.mj.KEY_UP)
            if mujoco.mj.KEY_DOWN in keys:
                cmd_vel[0] = max(cmd_vel[0] - KEY_STEP, VEL_X_RANGE[0])
                key_state["pressed"].discard(mujoco.mj.KEY_DOWN)
            if mujoco.mj.KEY_LEFT in keys:
                cmd_vel[1] = min(cmd_vel[1] + KEY_STEP, VEL_Y_RANGE[1])
                key_state["pressed"].discard(mujoco.mj.KEY_LEFT)
            if mujoco.mj.KEY_RIGHT in keys:
                cmd_vel[1] = max(cmd_vel[1] - KEY_STEP, VEL_Y_RANGE[0])
                key_state["pressed"].discard(mujoco.mj.KEY_RIGHT)

            # Note: keycodes for Z, X, C, R, 1, 2 are ASCII
            # We'll check them differently since they may vary by platform

            # Read sensors
            ang_vel = np.array(data.sensor("body_gyro").data[:3], dtype=np.float32)
            quat = np.array(data.sensor("body_quat").data[:4], dtype=np.float32)  # (w, x, y, z)

            # Read joint positions
            joint_pos = np.array([data.qpos[adr] for adr in joint_qpos_adr], dtype=np.float32)

            # Build observation
            obs = obs_builder.build(ang_vel, quat, cmd_vel, joint_pos, last_action)

            # Policy inference
            if policy is not None:
                raw_action = policy.forward(obs)
            else:
                raw_action = np.zeros(NUM_JOINTS, dtype=np.float32)

            last_action = raw_action.copy()

            # Compute target joint positions: scaled_action + default_pos
            target_pos = raw_action * action_scale + default_pos
            target_pos = np.clip(target_pos,
                                 np.array([model.jnt_range[i, 0] for i in range(model.njnt)
                                           if model.jnt_type[i] == mujoco.mjtJoint.mjJNT_HINGE]),
                                 np.array([model.jnt_range[i, 1] for i in range(model.njnt)
                                           if model.jnt_type[i] == mujoco.mjtJoint.mjJNT_HINGE]))

            # Set control (MuJoCo actuator PD handles the rest)
            data.ctrl[:] = target_pos

            # Step physics
            for _ in range(PHYSICS_STEPS_PER_POLICY):
                mujoco.mj_step(model, data)

            step_count += 1

            # Print status every second (50 steps)
            if step_count % 50 == 0:
                print(f"Step {step_count} | cmd_vel=({cmd_vel[0]:.2f}, {cmd_vel[1]:.2f}, {cmd_vel[2]:.2f}) "
                      f"| base_z={data.qpos[2]:.3f}")

            viewer.sync()


if __name__ == "__main__":
    main()
```

> **Note:** The keyboard callback API may vary across MuJoCo versions. The implementation above uses the `key_callback` parameter of `launch_passive`. If that doesn't work, alternatives include using `viewer.user_key` / `viewer.user_key_pressed` or a `pynput` keyboard listener in a separate thread. Adjust during implementation.

> **Note:** `mujoco.mj.KEY_UP` etc. are integer constants. If MuJoCo doesn't expose arrow key constants this way, use GLFW constants directly: `glfw.KEY_UP = 265`, `glfw.KEY_DOWN = 264`, `glfw.KEY_LEFT = 263`, `glfw.KEY_RIGHT = 266`. Add `glfw` as a dependency if needed (it's bundled with mujoco's viewer).

**Step 2: Verify it runs (no policy)**

First, pull the LFS policy files if not done:
```bash
cd /Users/lijialun/work/pupperv3-monorepo
git lfs pull --include="ros2_ws/src/neural_controller/launch/policy_latest.json"
```

Run without policy to verify MuJoCo loads and renders:
```bash
cd sim && uv run python pupperv3_sim.py
```
Expected: MuJoCo viewer opens, robot visible, standing at default pose, no movement (zero actions).

**Step 3: Verify with policy**

```bash
cd sim && uv run python pupperv3_sim.py ../ros2_ws/src/neural_controller/launch/policy_latest.json
```
Expected: Robot stands and walks in place (zero cmd_vel). Use arrow keys to move.

**Step 4: Commit**

```bash
git add sim/pupperv3_sim.py
git commit -m "feat(sim): add main simulation script with keyboard control"
```

---

### Task 6: Integration verification and fix

**Step 1: Run full simulation and verify robot doesn't fall**

Run: `cd sim && uv run python pupperv3_sim.py ../ros2_ws/src/neural_controller/launch/policy_latest.json`

Check:
- Robot stands stably at default pose
- Arrow keys produce directional movement
- Robot recovers from small perturbations (press C to zero cmd, then give commands again)
- Press R to reset → robot returns to standing pose

**Step 2: If robot falls, debug checklist**

In order of likelihood:
1. Print `data.ctrl` values — should be near `default_pos` when standing still
2. Print observation vector — gravity[2] should be near -1.0, joint_pos should be near 0.0
3. Verify `model.opt.timestep == 0.004`
4. Verify actuator `gainprm` and `biasprm` in loaded model: `print(model.actuator_gainprm[:3])` should show `[5, 0, 0]`
5. Verify total observation size matches `policy.input_size`
6. Check quaternion convention: `data.sensor("body_quat").data` should be `(w, x, y, z)`

**Step 3: Run all tests**

```bash
cd sim && uv run pytest test_policy.py test_observations.py -v
```

**Step 4: Final commit if fixes were needed**

```bash
git add -A sim/
git commit -m "fix(sim): integration fixes for stable locomotion"
```
