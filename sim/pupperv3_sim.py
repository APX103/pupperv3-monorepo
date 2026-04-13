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

    # Request OpenGL 3.3 core profile (needed for glBlitFramebuffer)
    glfw.window_hint(glfw.CONTEXT_VERSION_MAJOR, 3)
    glfw.window_hint(glfw.CONTEXT_VERSION_MINOR, 3)
    glfw.window_hint(glfw.OPENGL_PROFILE, glfw.OPENGL_CORE_PROFILE)
    glfw.window_hint(glfw.OPENGL_FORWARD_COMPAT, True)

    window = glfw.create_window(WINDOW_W, WINDOW_H, "Pupper V3 Sim", None, None)
    if not window:
        glfw.terminate()
        print("Failed to create GLFW window")
        sys.exit(1)

    glfw.make_context_current(window)
    glfw.swap_interval(1)

    # Create offscreen renderer
    renderer = mujoco.Renderer(model, width=WINDOW_W, height=WINDOW_H)
    renderer.enable_contact_rendering = True

    # Camera
    cam = mujoco.MjvCamera()
    cam.type = mujoco.mjtCamera.mjCAMERA_TRACKING
    cam.trackbodyid = 1  # base_link
    cam.distance = 1.5
    cam.elevation = -30

    # Keyboard state: process each key once on press
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

    # Mouse camera control state
    _button_left = False
    _button_middle = False
    _button_right = False
    _last_mouse = (0.0, 0.0)

    def on_mouse_button(window, button, action, mods):
        nonlocal _button_left, _button_middle, _button_right
        if action == glfw.PRESS:
            if button == glfw.MOUSE_BUTTON_LEFT:
                _button_left = True
            elif button == glfw.MOUSE_BUTTON_MIDDLE:
                _button_middle = True
            elif button == glfw.MOUSE_BUTTON_RIGHT:
                _button_right = True
        elif action == glfw.RELEASE:
            _button_left = _button_middle = _button_right = False

    def on_mouse_move(window, xpos, ypos):
        nonlocal _last_mouse
        dx = xpos - _last_mouse[0]
        dy = ypos - _last_mouse[1]
        _last_mouse = (xpos, ypos)

        if _button_right:
            cam.distance = max(0.3, cam.distance * (1 + dy * 0.005))
        elif _button_middle:
            cam.type = mujoco.mjtCamera.mjCAMERA_FREE
            cam.elevation = np.clip(cam.elevation - dy * 0.5, -90, 90)
            cam.azimuth += dx * 0.5

    def on_scroll(window, xoff, yoff):
        cam.distance = max(0.3, cam.distance * (1 - yoff * 0.05))

    glfw.set_mouse_button_callback(window, on_mouse_button)
    glfw.set_cursor_pos_callback(window, on_mouse_move)
    glfw.set_scroll_callback(window, on_scroll)

    # Track if window size changed
    def on_framebuffer_size(window, w, h):
        renderer.update_viewport(w, h)
        renderer.resize(w, h)

    glfw.set_framebuffer_size_callback(window, on_framebuffer_size)

    print("Running. Arrow keys: move, Z/X: yaw, C: zero vel, R: reset. Mouse: orbit/zoom.")

    # --- Main loop ---
    step_count = 0
    while not glfw.window_should_close(window):
        glfw.poll_events()

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
        target_pos = np.clip(raw_action * action_scale + default_pos, joint_lower, joint_upper)
        data.ctrl[:] = target_pos

        # Step physics
        for _ in range(PHYSICS_STEPS_PER_POLICY):
            mujoco.mj_step(model, data)

        step_count += 1

        # Render
        renderer.update_scene(data, camera=cam)
        renderer.render()
        framebuffer_width, framebuffer_height = glfw.get_framebuffer_size(window)
        renderer.update_viewport(framebuffer_width, framebuffer_height)

        # Blit offscreen render to GLFW window
        # The renderer renders to its own FBO; we need to display it on screen.
        # mujoco.Renderer.render_buffer stores the FBO ID.
        try:
            import ctypes
            GL_READ_FRAMEBUFFER = 0x8CA8
            GL_DRAW_FRAMEBUFFER = 0x8CA9
            GL_COLOR_BUFFER_BIT = 0x00004000
            GL_NEAREST = 0x2600

            gl = ctypes.cdll.LoadLibrary(
                "/System/Library/Frameworks/OpenGL.framework/OpenGL"
            )
            src_fbo = renderer.render_buffer
            gl.glBindFramebuffer(GL_READ_FRAMEBUFFER, ctypes.c_uint(src_fbo))
            gl.glBindFramebuffer(GL_DRAW_FRAMEBUFFER, ctypes.c_uint(0))
            gl.glBlitFramebuffer(
                ctypes.c_int(0), ctypes.c_int(0),
                ctypes.c_int(framebuffer_width), ctypes.c_int(framebuffer_height),
                ctypes.c_int(0), ctypes.c_int(0),
                ctypes.c_int(framebuffer_width), ctypes.c_int(framebuffer_height),
                ctypes.c_uint(GL_COLOR_BUFFER_BIT), ctypes.c_uint(GL_NEAREST),
            )
        except Exception:
            pass  # blit not critical for basic functionality

        glfw.swap_buffers(window)

        if step_count % 50 == 0:
            print(f"Step {step_count} | cmd=({cmd_vel[0]:+.2f},{cmd_vel[1]:+.2f},{cmd_vel[2]:+.2f}) "
                  f"| z={data.qpos[2]:.3f}")

    renderer.close()
    glfw.terminate()


if __name__ == "__main__":
    main()
