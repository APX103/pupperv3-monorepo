"""Standalone MuJoCo simulation for Pupper V3 with keyboard and ZMQ control."""

import argparse
import sys
import time
from pathlib import Path

import glfw
import mujoco
import numpy as np

from config import (
    ACTION_SCALE_DEFAULT,
    DEFAULT_JOINT_POS,
    JOINT_NAMES,
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
ANIMATIONS_DIR = REPO_ROOT / "ros2_ws/src/animation_controller_py/launch/animations"

# ZMQ command socket address
ZMQ_CMD_ADDR = "ipc:///tmp/pupper_sim_cmd"

WINDOW_W, WINDOW_H = 1280, 720


def find_animation_csv(name: str) -> Path:
    matches = list(ANIMATIONS_DIR.glob(f"{name}*.csv"))
    if len(matches) == 1:
        return matches[0]
    if len(matches) > 1:
        print(f"Multiple matches for '{name}':")
        for m in matches:
            print(f"  {m.name}")
        sys.exit(1)
    print(f"No animation found matching '{name}'")
    print("Available animations:")
    for f in sorted(ANIMATIONS_DIR.glob("*.csv")):
        print(f"  {f.stem.split('_recording')[0]}")
    sys.exit(1)


def load_animation(csv_path: Path):
    import csv as csv_mod

    with open(csv_path) as f:
        reader = csv_mod.reader(f)
        header = next(reader)
        csv_col_to_sim_idx = {}
        for col_idx, col_name in enumerate(header[2:]):
            if col_name in JOINT_NAMES:
                csv_col_to_sim_idx[col_idx] = JOINT_NAMES.index(col_name)
        timestamps = []
        joint_data = []
        for row in reader:
            timestamps.append(float(row[1]))
            joints = np.zeros(NUM_JOINTS, dtype=np.float64)
            for col_idx, sim_idx in csv_col_to_sim_idx.items():
                joints[sim_idx] = float(row[col_idx + 2])
            joint_data.append(joints)

    keyframes = np.array(joint_data)
    if len(timestamps) > 1:
        frame_rate = 1.0 / np.median(np.diff(timestamps))
    else:
        frame_rate = 30.0
    return keyframes, frame_rate


def interpolate_keyframes(keyframes, frame_rate, elapsed):
    total = len(keyframes)
    duration = (total - 1) / frame_rate
    if elapsed >= duration:
        return keyframes[-1]
    exact = elapsed * frame_rate
    idx = int(exact)
    alpha = exact - idx
    if idx + 1 < total:
        return keyframes[idx] * (1 - alpha) + keyframes[idx + 1] * alpha
    return keyframes[idx]


def main():
    parser = argparse.ArgumentParser(description="Pupper V3 MuJoCo Simulation")
    parser.add_argument("policy", nargs="?", help="Path to policy JSON")
    parser.add_argument("--animation", help="Animation name (e.g. stand_sit_stand, push_up)")
    parser.add_argument("--zmq", action="store_true", help="Enable ZMQ command socket for external control")
    args = parser.parse_args()

    if args.animation and args.policy:
        print("Cannot use both --animation and policy. Choose one.")
        sys.exit(1)

    require_action = not args.zmq  # --zmq mode can start idle, wait for commands

    xml_path = REPO_ROOT / MODEL_XML

    # Load MuJoCo model
    model = mujoco.MjModel.from_xml_path(str(xml_path))
    model.opt.timestep = PHYSICS_DT
    data = mujoco.MjData(model)

    # Load animation or policy
    keyframes = None
    frame_rate = 0.0
    if args.animation:
        csv_path = find_animation_csv(args.animation)
        keyframes, frame_rate = load_animation(csv_path)
        print(f"Loaded animation: {csv_path.name} ({len(keyframes)} frames, {frame_rate:.1f}Hz)")
        policy = None
        default_pos = np.array(DEFAULT_JOINT_POS, dtype=np.float32)
    elif args.policy:
        policy = RTNeuralPolicy(args.policy)
        print(f"Loaded policy: input={policy.input_size}, output={policy.output_size}, "
              f"history={policy.observation_history}, action_scale={policy.action_scale}")
    elif require_action:
        print("No policy or animation provided.")
        print("Usage: python pupperv3_sim.py <policy.json>")
        print("       python pupperv3_sim.py --animation <name>")
        print("       python pupperv3_sim.py --zmq [<policy.json>]")
        parser.print_help()
        sys.exit(1)
    else:
        # --zmq mode without policy: start idle, wait for commands
        policy = None
        print("ZMQ mode: waiting for external commands (animation/move/stop)")

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
    anim_start_time = None
    anim_done_printed = False
    anim_blend_start = None  # joint positions when animation started (for blending)
    ANIM_BLEND_DURATION = 1.0  # seconds to blend from current pose into new animation

    # Move command timer (for timed moves from ZMQ)
    move_end_time = 0.0

    # --- ZMQ command socket (optional) ---
    zmq_socket = None
    if args.zmq:
        import zmq
        zmq_ctx = zmq.Context()
        zmq_socket = zmq_ctx.socket(zmq.SUB)
        zmq_socket.connect(ZMQ_CMD_ADDR)
        zmq_socket.setsockopt_string(zmq.SUBSCRIBE, "")
        print(f"ZMQ command socket listening on {ZMQ_CMD_ADDR}")

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
            nonlocal anim_start_time, anim_done_printed, anim_blend_start
            anim_start_time = None
            anim_done_printed = False
            anim_blend_start = None
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

        # --- Poll ZMQ commands ---
        if zmq_socket is not None:
            while zmq_socket.poll(0, zmq.POLLIN):
                msg = zmq_socket.recv_json()
                cmd_type = msg.get("type", "")

                if cmd_type == "move":
                    vx = float(msg.get("vx", 0.0))
                    vy = float(msg.get("vy", 0.0))
                    wz = float(msg.get("wz", 0.0))
                    duration = float(msg.get("duration", 0.0))
                    cmd_vel[0] = np.clip(vx, VEL_X_RANGE[0], VEL_X_RANGE[1])
                    cmd_vel[1] = np.clip(vy, VEL_Y_RANGE[0], VEL_Y_RANGE[1])
                    cmd_vel[2] = np.clip(wz, VEL_YAW_RANGE[0], VEL_YAW_RANGE[1])
                    if duration > 0:
                        move_end_time = time.monotonic() + duration
                    print(f"[ZMQ] move: vx={vx}, vy={vy}, wz={wz}, dur={duration}")

                elif cmd_type == "animation":
                    csv_name = msg.get("name", "")
                    csv_path = ANIMATIONS_DIR / f"{csv_name}.csv"
                    if csv_path.exists():
                        keyframes, frame_rate = load_animation(csv_path)
                        anim_start_time = None
                        anim_done_printed = False
                        # Snapshot current joint positions for blending
                        anim_blend_start = np.array([data.qpos[adr] for adr in joint_qpos_adr], dtype=np.float32)
                        print(f"[ZMQ] animation: {csv_name} ({len(keyframes)} frames, {frame_rate:.1f}Hz)")
                    else:
                        print(f"[ZMQ] animation not found: {csv_path}")

                elif cmd_type == "stop":
                    cmd_vel[:] = 0.0
                    keyframes = None
                    anim_start_time = None
                    anim_done_printed = False
                    anim_blend_start = None
                    move_end_time = 0.0
                    print("[ZMQ] stop")

                elif cmd_type == "reset":
                    mujoco.mj_resetData(model, data)
                    for i, adr in enumerate(joint_qpos_adr):
                        data.qpos[adr] = default_pos[i]
                    mujoco.mj_forward(model, data)
                    last_action = np.zeros(NUM_JOINTS, dtype=np.float32)
                    cmd_vel[:] = 0.0
                    keyframes = None
                    anim_start_time = None
                    anim_done_printed = False
                    anim_blend_start = None
                    move_end_time = 0.0
                    print("[ZMQ] reset")

        # Auto-zero move command when timer expires
        if move_end_time > 0 and time.monotonic() >= move_end_time:
            cmd_vel[:] = 0.0
            move_end_time = 0.0

        # Read sensors
        ang_vel = np.array(data.sensor("body_gyro").data[:3], dtype=np.float32)
        quat = np.array(data.sensor("body_quat").data[:4], dtype=np.float32)
        joint_pos = np.array([data.qpos[adr] for adr in joint_qpos_adr], dtype=np.float32)

        # Compute target positions
        if keyframes is not None:
            if anim_start_time is None:
                anim_start_time = data.time
            elapsed = data.time - anim_start_time
            target_pos = interpolate_keyframes(keyframes, frame_rate, elapsed).astype(np.float32)
            # Blend from current pose into animation over ANIM_BLEND_DURATION
            if anim_blend_start is not None and elapsed < ANIM_BLEND_DURATION:
                alpha = elapsed / ANIM_BLEND_DURATION
                # Smooth step (ease in-out)
                alpha = alpha * alpha * (3.0 - 2.0 * alpha)
                target_pos = (1.0 - alpha) * anim_blend_start + alpha * target_pos
            else:
                anim_blend_start = None
            if elapsed >= (len(keyframes) - 1) / frame_rate and not anim_done_printed:
                print("Animation complete. Holding last frame.")
                anim_done_printed = True
            data.ctrl[:] = np.clip(target_pos, joint_lower, joint_upper)
        else:
            obs = obs_builder.build(ang_vel, quat, cmd_vel, joint_pos, last_action)
            if policy is not None:
                raw_action = policy.forward(obs)
            else:
                raw_action = np.zeros(NUM_JOINTS, dtype=np.float32)
            last_action = raw_action.copy()
            target_pos = np.clip(raw_action * action_scale + default_pos, joint_lower, joint_upper)
            data.ctrl[:] = target_pos

        # Step physics
        for _ in range(PHYSICS_STEPS_PER_POLICY):
            mujoco.mj_step(model, data)

        step_count += 1

        # Render directly to GLFW window framebuffer
        fb_w, fb_h = glfw.get_framebuffer_size(window)
        viewport = mujoco.MjrRect(0, 0, fb_w, fb_h)

        mujoco.mjv_updateScene(model, data, vopt, perturb, cam, -1, scene)
        mujoco.mjr_render(viewport, scene, con)

        glfw.swap_buffers(window)

        if step_count % 50 == 0:
            print(f"Step {step_count} | cmd=({cmd_vel[0]:+.2f},{cmd_vel[1]:+.2f},{cmd_vel[2]:+.2f}) "
                  f"| z={data.qpos[2]:.3f}")

    con.free()
    glfw.terminate()


if __name__ == "__main__":
    main()
