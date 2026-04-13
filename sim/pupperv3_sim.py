"""Standalone MuJoCo simulation for Pupper V3 with keyboard control."""

import sys
from pathlib import Path

import glfw
import mujoco
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
    VEL_X_RANGE,
    VEL_Y_RANGE,
    VEL_YAW_RANGE,
)
from observations import ObservationBuilder
from policy import RTNeuralPolicy

REPO_ROOT = Path(__file__).resolve().parent.parent

WINDOW_W, WINDOW_H = 1280, 720


def main():
    policy_path = sys.argv[1] if len(sys.argv) > 1 else None
    xml_path = REPO_ROOT / MODEL_XML

    # Load MuJoCo model
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
        print("Usage: python pupperv3_sim.py <policy.json>")
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

    # Init robot pose
    mujoco.mj_resetData(model, data)
    for i, adr in enumerate(joint_qpos_adr):
        data.qpos[adr] = default_pos[i]
    mujoco.mj_forward(model, data)

    # --- GLFW setup ---
    if not glfw.init():
        print("Failed to initialize GLFW")
        sys.exit(1)

    window = glfw.create_window(WINDOW_W, WINDOW_H, "Pupper V3 Sim", None, None)
    if not window:
        glfw.terminate()
        print("Failed to create GLFW window")
        sys.exit(1)

    glfw.make_context_current(window)
    glfw.swap_interval(1)

    # --- MuJoCo rendering (direct to GLFW window, no offscreen) ---
    con = mujoco.MjrContext(model, mujoco.mjtFontScale.mjFONTSCALE_150)
    scene = mujoco.MjvScene(model, maxgeom=10000)
    vopt = mujoco.MjvOption()
    vopt.flags[mujoco.mjtVisFlag.mjVIS_CONTACTPOINT] = True
    perturb = mujoco.MjvPerturb()

    # Camera
    cam = mujoco.MjvCamera()
    cam.type = mujoco.mjtCamera.mjCAMERA_TRACKING
    cam.trackbodyid = 1
    cam.distance = 1.5
    cam.elevation = -30

    # Keyboard
    def on_key(window, key, scancode, action, mods):
        nonlocal cmd_vel, last_action
        if action != glfw.PRESS:
            return
        step = 0.05
        if key == glfw.KEY_UP:
            cmd_vel[0] = min(cmd_vel[0] + step, VEL_X_RANGE[1])
        elif key == glfw.KEY_DOWN:
            cmd_vel[0] = max(cmd_vel[0] - step, VEL_X_RANGE[0])
        elif key == glfw.KEY_LEFT:
            cmd_vel[1] = min(cmd_vel[1] + step, VEL_Y_RANGE[1])
        elif key == glfw.KEY_RIGHT:
            cmd_vel[1] = max(cmd_vel[1] - step, VEL_Y_RANGE[0])
        elif key == glfw.KEY_Z:
            cmd_vel[2] = min(cmd_vel[2] + 0.1, VEL_YAW_RANGE[1])
        elif key == glfw.KEY_X:
            cmd_vel[2] = max(cmd_vel[2] - 0.1, VEL_YAW_RANGE[0])
        elif key == glfw.KEY_C:
            cmd_vel[:] = 0.0
        elif key == glfw.KEY_R:
            mujoco.mj_resetData(model, data)
            for i, adr in enumerate(joint_qpos_adr):
                data.qpos[adr] = default_pos[i]
            mujoco.mj_forward(model, data)
            last_action = np.zeros(NUM_JOINTS, dtype=np.float32)
            print("Reset.")

    glfw.set_key_callback(window, on_key)

    # Mouse camera control
    _last_mouse = [0.0, 0.0]
    _button = [0, 0, 0]  # left, middle, right
    _scroll = [0]

    def on_mouse_button(window, button, action, mods):
        if action == glfw.PRESS:
            if button == glfw.MOUSE_BUTTON_LEFT:
                _button[0] = 1
            elif button == glfw.MOUSE_BUTTON_MIDDLE:
                _button[1] = 1
            elif button == glfw.MOUSE_BUTTON_RIGHT:
                _button[2] = 1
        elif action == glfw.RELEASE:
            _button[0] = _button[1] = _button[2] = 0

    def on_mouse_move(window, xpos, ypos):
        dx = xpos - _last_mouse[0]
        dy = ypos - _last_mouse[1]
        _last_mouse[0] = xpos
        _last_mouse[1] = ypos

        width, height = glfw.get_window_size(window)
        if width == 0 or height == 0:
            return

        if _button[0]:
            action = mujoco.mjtMouse.mjMOUSE_ROTATE_V
        elif _button[1]:
            action = mujoco.mjtMouse.mjMOUSE_MOVE_V
        elif _button[2]:
            action = mujoco.mjtMouse.mjMOUSE_ZOOM
        else:
            return

        mujoco.mjv_moveCamera(
            model, action, dx / width, dy / height, scene, cam,
        )

    def on_scroll(window, xoff, yoff):
        width, height = glfw.get_window_size(window)
        if width == 0 or height == 0:
            return
        mujoco.mjv_moveCamera(
            model, mujoco.mjtMouse.mjMOUSE_ZOOM, 0, -0.05 * yoff, scene, cam,
        )

    glfw.set_mouse_button_callback(window, on_mouse_button)
    glfw.set_cursor_pos_callback(window, on_mouse_move)
    glfw.set_scroll_callback(window, on_scroll)

    print("Running. Arrow keys: move, Z/X: yaw, C: zero vel, R: reset. Mouse: orbit/zoom.")

    # --- Main loop ---
    step_count = 0
    while not glfw.window_should_close(window):
        glfw.poll_events()

        # Read sensors
        ang_vel = np.array(data.sensor("body_gyro").data[:3], dtype=np.float32)
        quat = np.array(data.sensor("body_quat").data[:4], dtype=np.float32)
        joint_pos = np.array([data.qpos[adr] for adr in joint_qpos_adr], dtype=np.float32)

        # Build observation and run policy
        obs = obs_builder.build(ang_vel, quat, cmd_vel, joint_pos, last_action)

        if policy is not None:
            raw_action = policy.forward(obs)
        else:
            raw_action = np.zeros(NUM_JOINTS, dtype=np.float32)

        last_action = raw_action.copy()

        # Target position = scaled action + default
        target_pos = np.clip(raw_action * action_scale + default_pos, joint_lower, joint_upper)
        data.ctrl[:] = target_pos

        # Step physics
        for _ in range(PHYSICS_STEPS_PER_POLICY):
            mujoco.mj_step(model, data)

        step_count += 1

        # Render directly to GLFW window framebuffer
        fb_w, fb_h = glfw.get_framebuffer_size(window)
        viewport = mujoco.MjrRect(0, 0, fb_w, fb_h)

        mujoco.mjv_updateScene(model, data, vopt, perturb, cam, scene)
        mujoco.mjr_render(viewport, scene, con)

        glfw.swap_buffers(window)

        if step_count % 50 == 0:
            print(f"Step {step_count} | cmd=({cmd_vel[0]:+.2f},{cmd_vel[1]:+.2f},{cmd_vel[2]:+.2f}) "
                  f"| z={data.qpos[2]:.3f}")

    con.free()
    glfw.terminate()


if __name__ == "__main__":
    main()
