"""
Pupper V3 Pure MuJoCo Simulation with Keyboard Control

Usage:
    cd sim && uv run python run.py [--policy ../ros2_ws/src/neural_controller/launch/policy_latest.json]

Keyboard:
    W/S  - Forward/Backward
    A/D  - Strafe Left/Right
    Q/E  - Rotate Left/Right
    Space - E-Stop (kill all motor output)
    R    - Reset robot to home position
    Esc  - Quit

Keyboard (arrow keys, avoids MuJoCo viewer shortcuts):
    Up/Down  - Forward/Backward
    Left/Right - Strafe Left/Right
    PgUp/PgDn - Rotate Left/Right
"""

import argparse
import json
import math
import os
import sys
import time

import mujoco
import numpy as np

# ─── Paths ────────────────────────────────────────────────────────────

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_MJCF = os.path.join(
    REPO_ROOT,
    "ros2_ws/src/pupper_v3_description/description/mujoco_xml/model_with_obstacles.xml",
)
DEFAULT_POLICY = os.path.join(
    REPO_ROOT,
    "ros2_ws/src/neural_controller/launch/policy_latest.json",
)


# ─── Policy loader ───────────────────────────────────────────────────

def elu(x: np.ndarray) -> np.ndarray:
    return np.where(x > 0, x, np.exp(x) - 1)


class Policy:
    """Loads a Haiku-exported JSON policy and runs inference with numpy."""

    def __init__(self, path: str):
        with open(path) as f:
            data = json.load(f)

        self.observation_history: int = data["observation_history"]
        self.action_scale: float = data["action_scale"]
        self.default_joint_pos = np.array(data["default_joint_pos"], dtype=np.float32)
        self.joint_upper = np.array(data["joint_upper_limits"], dtype=np.float32)
        self.joint_lower = np.array(data["joint_lower_limits"], dtype=np.float32)
        self.use_imu: bool = data.get("use_imu", True)
        self.control_orientation: bool = data.get("control_orientation", True)
        self.kp: float = data.get("kp", 5.0)
        self.kd: float = data.get("kd", 0.25)

        # Build layers: list of (W, b, activation_fn)
        self.layers: list[tuple[np.ndarray, np.ndarray, callable]] = []
        for layer in data["layers"]:
            W = np.array(layer["weights"][0], dtype=np.float32)
            b = np.array(layer["weights"][1], dtype=np.float32)
            act = elu if layer["activation"] == "elu" else np.tanh
            self.layers.append((W, b, act))

        # Observation history buffer
        obs_dim = 36
        self.obs_size = self.observation_history * obs_dim  # 720
        self.obs_buf = np.zeros(self.obs_size, dtype=np.float32)
        # Initialize standing observation for every history frame:
        #   gravity_body[2] = -1.0 (index 5)
        #   desired_z[2] = 1.0 (index 11)
        for t in range(self.observation_history):
            self.obs_buf[t * obs_dim + 5] = -1.0   # gravity Z
            self.obs_buf[t * obs_dim + 11] = 1.0   # desired Z

        # Previous action buffer (one per history frame, init zeros)
        self.prev_action = np.zeros(12, dtype=np.float32)

        print(f"[Policy] Loaded: {len(self.layers)} layers, "
              f"obs={self.obs_size}, history={self.observation_history}")

    def step(self, ang_vel, gravity, cmd_vel, desired_z, joint_pos):
        """
        Compute one policy step.

        Args:
            ang_vel: (3,) body angular velocity
            gravity: (3,) projected gravity in body frame
            cmd_vel: (3,) [x_vel, y_vel, yaw_vel]
            desired_z: (3,) desired world Z-axis in body frame
            joint_pos: (12,) current joint positions
        """
        obs_dim = 36
        # Build single observation (36-dim)
        obs = np.zeros(obs_dim, dtype=np.float32)
        obs[0:3] = ang_vel
        obs[3:6] = gravity
        obs[6:9] = cmd_vel
        obs[9:12] = desired_z
        obs[12:24] = joint_pos - self.default_joint_pos
        obs[24:36] = self.prev_action

        # Shift history buffer right by one frame and insert new observation at front
        self.obs_buf[obs_dim:] = self.obs_buf[:-obs_dim]
        self.obs_buf[:obs_dim] = obs

        # Forward pass
        x = self.obs_buf.copy()
        for W, b, act in self.layers:
            x = act(x @ W + b)

        return x

    def reset(self):
        self.obs_buf[:] = 0
        for t in range(self.observation_history):
            self.obs_buf[t * 36 + 5] = -1.0   # gravity Z
            self.obs_buf[t * 36 + 11] = 1.0   # desired Z
        self.prev_action[:] = 0


# ─── Keyboard handler ────────────────────────────────────────────────

class Keyboard:
    """Simple keyboard state tracker using Windows msvcrt."""

    def __init__(self):
        self.cmd_vel = np.zeros(3, dtype=np.float32)  # [x, y, yaw]
        self.estop = False
        self.reset = False
        self.quit = False
        self._max_lin = 0.75
        self._max_yaw = 2.0

    def update(self):
        try:
            import msvcrt
        except ImportError:
            return

        while msvcrt.kbhit():
            ch = msvcrt.getch()
            if ch == b'\x1b':  # Esc
                self.quit = True
                break
            elif ch == b' ':
                self.estop = not self.estop
            elif ch == b'r':
                self.reset = True
            else:
                key = ch.decode("ascii", errors="ignore").lower()

        # Continuous check for held keys - use a simpler approach
        # We poll key state for WASDQE using GetAsyncKeyState
        import ctypes
        vk_map = {
            0x57: "w", 0x53: "s", 0x41: "a", 0x44: "d", 0x51: "q", 0x45: "e",
            0x20: "space", 0x52: "r", 0x1b: "esc",
            0x26: "up", 0x28: "down", 0x25: "left", 0x27: "right",
            0x21: "pgup", 0x22: "pgdn",
        }
        held = set()
        for vk, name in vk_map.items():
            if ctypes.windll.user32.GetAsyncKeyState(vk) & 0x8000:
                held.add(name)

        vx = self._max_lin * ((1.0 if "up" in held else 0.0) - (1.0 if "down" in held else 0.0))
        vy = self._max_lin * ((1.0 if "left" in held else 0.0) - (1.0 if "right" in held else 0.0)) * 0.5
        yaw = self._max_yaw * ((1.0 if "pgdn" in held else 0.0) - (1.0 if "pgup" in held else 0.0))

        # Smooth towards target
        alpha = 0.3
        self.cmd_vel[0] += alpha * (vx - self.cmd_vel[0])
        self.cmd_vel[1] += alpha * (vy - self.cmd_vel[1])
        self.cmd_vel[2] += alpha * (yaw - self.cmd_vel[2])

        if "esc" in held:
            self.quit = True
        if "space" in held:
            self.estop = True
        elif "space" not in held:
            self.estop = False


# ─── Simulation ──────────────────────────────────────────────────────

def quat_to_gravity(q: np.ndarray) -> np.ndarray:
    """Rotate world gravity [0,0,-1] into body frame using quaternion [w,x,y,z]."""
    w, x, y, z = q
    # Rotation matrix from quaternion
    R = np.array([
        [1 - 2*(y*y + z*z), 2*(x*y - w*z),     2*(x*z + w*y)],
        [2*(x*y + w*z),     1 - 2*(x*x + z*z), 2*(y*z - w*x)],
        [2*(x*z - w*y),     2*(y*z + w*x),     1 - 2*(x*x + y*y)],
    ], dtype=np.float32)
    # World gravity in body frame
    g_body = R @ np.array([0.0, 0.0, -1.0], dtype=np.float32)
    return g_body


def quat_rotate_inverse(q: np.ndarray, v: np.ndarray) -> np.ndarray:
    """Rotate vector v from world to body frame using quaternion [w,x,y,z]."""
    return quat_to_gravity(q) * (-np.linalg.norm(v))  # Not quite right for general v


def quat_rotate(q: np.ndarray, v: np.ndarray) -> np.ndarray:
    """Rotate vector v from body to world frame."""
    w, x, y, z = q
    R = np.array([
        [1 - 2*(y*y + z*z), 2*(x*y - w*z),     2*(x*z + w*y)],
        [2*(x*y + w*z),     1 - 2*(x*x + z*z), 2*(y*z - w*x)],
        [2*(x*z - w*y),     2*(y*z + w*x),     1 - 2*(x*x + y*y)],
    ], dtype=np.float32)
    return R @ v


def find_sensor_id(model, name: str) -> int:
    """Find sensor data address by name."""
    for i in range(model.nsensor):
        if model.sensor(i).name == name:
            return model.sensor_adr[i]
    raise ValueError(f"Sensor '{name}' not found")


def run(mjcf_path: str, policy_path: str):
    # Fix mesh directory in XML
    with open(mjcf_path) as f:
        xml = f.read()

    mesh_dir = os.path.join(os.path.dirname(mjcf_path), "../meshes/stl/")
    mesh_dir = os.path.normpath(mesh_dir).replace("\\", "/")

    # Patch the meshdir to be absolute
    import re
    xml = re.sub(r'meshdir="[^"]*"', f'meshdir="{mesh_dir}"', xml)

    model = mujoco.MjModel.from_xml_string(xml)
    data = mujoco.MjData(model)

    # Convert actuators to pure torque mode (mimics actuator_model.hpp behavior)
    # Original: force = 5*(ctrl-qpos) - 0.1*qvel (position actuator)
    # We want:  force = ctrl (torque command), PD computed in Python
    for i in range(model.nu):
        model.actuator(i).gainprm[0] = 1.0
        model.actuator(i).biasprm[0] = 0.0
        model.actuator(i).biasprm[1] = 0.0
        model.actuator(i).biasprm[2] = 0.0

    policy = Policy(policy_path)
    keyboard = Keyboard()

    # Joint name ordering
    joint_names = [
        "leg_front_r_1", "leg_front_r_2", "leg_front_r_3",
        "leg_front_l_1", "leg_front_l_2", "leg_front_l_3",
        "leg_back_r_1",  "leg_back_r_2",  "leg_back_r_3",
        "leg_back_l_1",  "leg_back_l_2",  "leg_back_l_3",
    ]
    joint_ids = [mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_JOINT, n) for n in joint_names]

    # Sensor IDs
    gyro_id = find_sensor_id(model, "body_gyro")
    quat_id = find_sensor_id(model, "body_quat")

    # Print info
    nq = model.nq
    nv = model.nv
    nu = model.nu
    print(f"[Sim] Model: {model.nbody} bodies, {model.njnt} joints, "
          f"{nu} actuators, dt={model.opt.timestep}s")
    print(f"[Sim] qpos={nq}, qvel={nv}, n_sensor={model.nsensor}")

    # Create viewer
    from mujoco import viewer as _viewer
    viewer = _viewer.launch_passive(model, data)

    # Simulation timing
    policy_hz = 50
    sim_steps_per_policy = int(1.0 / (policy_hz * model.opt.timestep))  # ~5 steps at 0.004s

    step_count = 0
    init_duration = 1.0     # seconds: interpolate from keyframe to default
    fade_in_duration = 1.0  # seconds: ramp policy output

    # Actuator params (from actuator_model.hpp via ros2_control xacro)
    kp = 7.5
    kd = 0.25
    bus_voltage = 24.0
    kt = 0.04
    phase_resistance = 0.7
    saturation_torque = 4.5
    software_torque_limit = 3.0

    # Init: set to keyframe "home" (body at z=0.28, joints=0, feet on ground)
    mujoco.mj_resetData(model, data)
    data.qpos[0:3] = [0.0, 0.0, 0.28]       # body position
    data.qpos[3:7] = [1.0, 0.0, 0.0, 0.0]    # body quaternion
    data.qpos[7:] = 0.0                         # all joints = 0
    mujoco.mj_forward(model, data)
    init_joint_pos = np.zeros(12, dtype=np.float32)  # keyframe joints are 0
    target = init_joint_pos.copy()

    policy.reset()
    start_time = time.time()

    print("[Sim] Running... Arrows=move, PgUp/PgDn=rotate, Space=estop, R=reset, Esc=quit")

    while viewer.is_running() and not keyboard.quit:
        keyboard.update()

        # Handle reset
        if keyboard.reset:
            mujoco.mj_resetData(model, data)
            data.qpos[0:3] = [0.0, 0.0, 0.28]
            data.qpos[3:7] = [1.0, 0.0, 0.0, 0.0]
            data.qpos[7:] = 0.0
            mujoco.mj_forward(model, data)
            target = np.zeros(12, dtype=np.float32)
            policy.reset()
            start_time = time.time()
            keyboard.reset = False
            print("[Sim] Reset!")

        # Read sensors
        quat = data.sensordata[quat_id:quat_id + 4].copy()  # [w, x, y, z]
        w, x, y, z = quat

        # Rotation matrix (world → body)
        R = np.array([
            [1 - 2*(y*y + z*z), 2*(x*y - w*z),     2*(x*z + w*y)],
            [2*(x*y + w*z),     1 - 2*(x*x + z*z), 2*(y*z - w*x)],
            [2*(x*z - w*y),     2*(y*z + w*x),     1 - 2*(x*x + y*y)],
        ], dtype=np.float32)

        # Project gravity to body frame and L2-normalize (matches training env)
        gravity_body = R @ np.array([0.0, 0.0, -1.0], dtype=np.float32)
        gravity_body = gravity_body / (np.linalg.norm(gravity_body) + 1e-8)

        # MuJoCo <gyro> already returns body-frame angular velocity
        gyro_body = data.sensordata[gyro_id:gyro_id + 3].copy()

        # Desired Z in body frame = R column 2
        desired_z = R[:, 2].copy()

        # Joint positions and velocities
        joint_pos = np.array([data.qpos[model.jnt_qposadr[jid]] for jid in joint_ids], dtype=np.float32)
        joint_vel = np.array([data.qvel[model.jnt_dofadr[jid]] for jid in joint_ids], dtype=np.float32)

        # Update target at policy_hz (50Hz)
        if step_count % sim_steps_per_policy == 0:
            elapsed = time.time() - start_time

            if elapsed < init_duration:
                # INIT PHASE: interpolate from keyframe pose to default_joint_pos
                alpha = elapsed / init_duration
                target = init_joint_pos * (1.0 - alpha) + policy.default_joint_pos * alpha
            else:
                # FADE-IN PHASE: run policy with gradual ramp
                fade_in = min(1.0, (elapsed - init_duration) / fade_in_duration)
                policy_step_num = int((elapsed - init_duration) * policy_hz)

                raw_action = policy.step(
                    ang_vel=gyro_body,
                    gravity=gravity_body,
                    cmd_vel=keyboard.cmd_vel if not keyboard.estop else np.zeros(3),
                    desired_z=desired_z,
                    joint_pos=joint_pos,
                )

                if policy_step_num < 3:
                    jd = joint_pos - policy.default_joint_pos
                    print(f"[P{policy_step_num}] fi={fade_in:.3f} gyro={gyro_body} grav={gravity_body}")
                    print(f"         jdev={[f'{v:+.3f}' for v in jd]}")
                    print(f"         raw={[f'{v:+.3f}' for v in raw_action]} tgt={[f'{v:+.3f}' for v in target]}")

                scaled_action = fade_in * raw_action
                target = scaled_action * policy.action_scale + policy.default_joint_pos
                target = np.clip(target, policy.joint_lower, policy.joint_upper)

                if keyboard.estop:
                    target = policy.default_joint_pos.copy()
                    scaled_action = np.zeros(12, dtype=np.float32)

                policy.prev_action = scaled_action

        # Compute PD torque EVERY physics step
        for i in range(12):
            torque = kp * (target[i] - joint_pos[i]) + kd * (0.0 - joint_vel[i])
            torque = np.clip(torque, -software_torque_limit, software_torque_limit)
            emf = abs(kt * joint_vel[i])
            max_current = (bus_voltage - emf) / phase_resistance
            emf_limited_torque = max_current * kt
            torque = np.clip(torque, -emf_limited_torque, emf_limited_torque)
            torque = np.clip(torque, -saturation_torque, saturation_torque)
            data.ctrl[i] = torque

        # Step simulation
        mujoco.mj_step(model, data)
        step_count += 1

        # Sync viewer (throttle to real-time)
        viewer.sync()

    viewer.close()
    print("[Sim] Done.")


# ─── Entry point ─────────────────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Pupper V3 MuJoCo Simulation")
    parser.add_argument("--policy", default=DEFAULT_POLICY, help="Path to policy JSON")
    parser.add_argument("--model", default=DEFAULT_MJCF, help="Path to MuJoCo XML")
    args = parser.parse_args()

    if not os.path.exists(args.policy):
        print(f"Error: Policy not found: {args.policy}", file=sys.stderr)
        sys.exit(1)
    if not os.path.exists(args.model):
        print(f"Error: Model not found: {args.model}", file=sys.stderr)
        sys.exit(1)

    run(args.model, args.policy)
