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
        print(f"Loaded policy: input={policy.input_size}, output={policy.output_size}, "
              f"history={policy.observation_history}, action_scale={policy.action_scale}")
    else:
        print("No policy provided. Running with zero actions.")
        print(f"Usage: python pupperv3_sim.py <policy.json>")
        policy = None

    # Resolve parameters from policy JSON or defaults
    default_pos = policy.default_joint_pos if policy else np.array(DEFAULT_JOINT_POS, dtype=np.float32)
    action_scale = policy.action_scale if policy else ACTION_SCALE_DEFAULT
    history = policy.observation_history if policy else OBSERVATION_HISTORY_DEFAULT

    # Find hinge joint qpos addresses (skip freejoint)
    joint_qpos_adr = []
    joint_ranges = []
    for i in range(model.njnt):
        if model.jnt_type[i] == mujoco.mjtJoint.mjJNT_HINGE:
            joint_qpos_adr.append(model.jnt_qposadr[i])
            joint_ranges.append((model.jnt_range[i, 0], model.jnt_range[i, 1]))
    assert len(joint_qpos_adr) == NUM_JOINTS, \
        f"Expected {NUM_JOINTS} hinge joints, got {len(joint_qpos_adr)}"
    joint_lower = np.array([r[0] for r in joint_ranges])
    joint_upper = np.array([r[1] for r in joint_ranges])

    # Observation builder
    obs_builder = ObservationBuilder(history=history, default_pos=default_pos, clip=OBSERVATION_LIMIT)

    # State
    cmd_vel = np.array([0.0, 0.0, 0.0], dtype=np.float32)
    last_action = np.zeros(NUM_JOINTS, dtype=np.float32)

    def reset():
        nonlocal last_action
        mujoco.mj_resetData(model, data)
        for i, adr in enumerate(joint_qpos_adr):
            data.qpos[adr] = default_pos[i]
        mujoco.mj_forward(model, data)
        last_action = np.zeros(NUM_JOINTS, dtype=np.float32)

    reset()

    # Keyboard constants (GLFW)
    KEY_UP = 265
    KEY_DOWN = 264
    KEY_LEFT = 263
    KEY_RIGHT = 266

    def key_callback(keycode):
        nonlocal cmd_vel
        step = 0.05
        if keycode == KEY_UP:
            cmd_vel[0] = min(cmd_vel[0] + step, VEL_X_RANGE[1])
        elif keycode == KEY_DOWN:
            cmd_vel[0] = max(cmd_vel[0] - step, VEL_X_RANGE[0])
        elif keycode == KEY_LEFT:
            cmd_vel[1] = min(cmd_vel[1] + step, VEL_Y_RANGE[1])
        elif keycode == KEY_RIGHT:
            cmd_vel[1] = max(cmd_vel[1] - step, VEL_Y_RANGE[0])
        elif keycode == ord('Z'):
            cmd_vel[2] = min(cmd_vel[2] + 0.1, VEL_YAW_RANGE[1])
        elif keycode == ord('X'):
            cmd_vel[2] = max(cmd_vel[2] - 0.1, VEL_YAW_RANGE[0])
        elif keycode == ord('C'):
            cmd_vel[:] = 0.0
        elif keycode == ord('R'):
            reset()

    # Launch viewer
    # Try key_callback kwarg first (newer mujoco); fall back to attribute assignment
    try:
        viewer_ctx = mujoco.viewer.launch_passive(model, data, key_callback=key_callback)
    except TypeError:
        viewer_ctx = mujoco.viewer.launch_passive(model, data)
        viewer_ctx.user_key_callback = key_callback

    with viewer_ctx as viewer:
        viewer.opt.flags[mujoco.mjtVisFlag.mjVIS_CONTACTPOINT] = True

        step_count = 0
        while viewer.is_running():
            # Read sensors
            ang_vel = np.array(data.sensor("body_gyro").data[:3], dtype=np.float32)
            quat = np.array(data.sensor("body_quat").data[:4], dtype=np.float32)

            # Read joint positions
            joint_pos = np.array([data.qpos[adr] for adr in joint_qpos_adr], dtype=np.float32)

            # Build observation and run policy
            obs = obs_builder.build(ang_vel, quat, cmd_vel, joint_pos, last_action)

            if policy is not None:
                raw_action = policy.forward(obs)
            else:
                raw_action = np.zeros(NUM_JOINTS, dtype=np.float32)

            last_action = raw_action.copy()

            # Target position = scaled action + default
            target_pos = np.clip(
                raw_action * action_scale + default_pos,
                joint_lower,
                joint_upper,
            )

            # Set control (MuJoCo actuator PD handles the rest)
            data.ctrl[:] = target_pos

            # Step physics
            for _ in range(PHYSICS_STEPS_PER_POLICY):
                mujoco.mj_step(model, data)

            step_count += 1
            if step_count % 50 == 0:
                print(f"Step {step_count} | cmd=({cmd_vel[0]:+.2f},{cmd_vel[1]:+.2f},{cmd_vel[2]:+.2f}) "
                      f"| z={data.qpos[2]:.3f}")

            viewer.sync()


if __name__ == "__main__":
    main()
