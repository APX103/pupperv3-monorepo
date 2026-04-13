# Standalone MuJoCo Simulation Design

## Overview

Create a standalone MuJoCo simulation in `sim/` that loads the trained RL policy and allows keyboard control, completely independent of ROS2.

## Architecture

```
sim/
├── pyproject.toml          # uv project (mujoco, numpy)
├── pupperv3_sim.py         # Main entry: sim loop, keyboard, rendering
├── policy.py               # RTNeural JSON loader + NumPy forward pass
├── observations.py         # 192-dim observation builder
└── config.py               # Constants from ROS2 config.yaml
```

MuJoCo XML: directly use existing `pupper_v3_complete.mjx.position.xml` from `ros2_ws/src/pupper_v3_description/description/mujoco_xml/`.

## Control Flow

```
Startup → load XML + policy JSON → init joints to default_joint_pos
  ↓
Main loop (50 Hz policy, 5 × 0.004s physics steps per policy step):
  1. Read IMU: gyro (ang_vel) + framequat → projected gravity
  2. Read joint positions → normalize (q - default_pos)
  3. Build observation (36-dim × history stacked, history rotation)
  4. Policy forward → 12-dim tanh output
  5. Scale: ctrl = output × action_scale + default_joint_pos
  6. MuJoCo stepper (actuator PD is built into XML)
  7. Keyboard updates cmd_vel
  8. viewer.render()
```

## Keyboard Mapping (no MuJoCo conflicts)

| Key | Action |
|-----|--------|
| `↑` / `↓` | Forward/backward (±0.1 m/s, max ±0.75) |
| `←` / `→` | Strafe left/right (±0.1 m/s, max ±0.5) |
| `Z` / `X` | Yaw left/right (±0.2 rad/s, max ±2.0) |
| `C` | Zero velocity command |
| `R` | Reset simulation |
| `1` / `2` | Switch 4-leg / 3-leg policy |

## Policy JSON Metadata

The policy JSON (RTNeural format) embeds these parameters that MUST be read from JSON:
- `in_shape`: `[1, N]` where N = observation_history × 36
- `observation_history`: number of history steps (typically 4)
- `default_joint_pos`: 12-element array
- `action_scale`: scalar or 12-element array (training: 0.75)
- `kp`, `kd`: scalar gain values
- `joint_lower_limits`, `joint_upper_limits`: 12-element arrays
- `use_imu`: boolean

## Constants (from training config)

- `default_joint_pos`: `[0.26, 0.0, -0.52, -0.26, 0.0, 0.52, 0.26, 0.0, -0.52, -0.26, 0.0, 0.52]`
- `action_scale`: 0.75
- Velocity ranges: x ∈ [-0.75, 0.75], y ∈ [-0.5, 0.5], yaw ∈ [-2.0, 2.0]
- `observation_limit`: 100.0 (clip)

---

# Potential Failure Points: Why Policy Falls in Sim But Works on Real Robot

These are the differences discovered between the three environments that could cause the policy to fail in a standalone sim. They are ordered by severity.

## CRITICAL: Must get right or the robot WILL fall

### 1. Actuator Model is Fundamentally Different

This is the #1 most likely cause of failure. The training XML and ROS2 XML define actuators completely differently.

**Training XML** (`pupper_v3_complete.mjx.position.xml`):
```xml
<general gainprm="5.0 0 0" biasprm="0 -5.0 -0.1" />
```
MuJoCo computes torque internally: `τ = 5.0 × ctrl + 0 - 5.0 × qpos - 0.1 × qvel`
→ Built-in PD control: **kp=5.0, kd=0.1**
→ `ctrl` = target joint position

**ROS2 XML** (`pupper_v3_complete.xml`):
```xml
<general gainprm="1 0 0" biasprm="0 0 0" />
```
MuJoCo computes: `τ = 1.0 × ctrl` → Raw torque output, **no PD**
→ PD control is implemented externally in C++ (hardware interface) with kp=7.5, kd=0.25
→ `ctrl` = torque command (after external PD computation)

**If standalone uses ROS2 XML + sets ctrl = target position**: MuJoCo applies raw torque
proportional to target position → no position holding → robot collapses immediately.

**If standalone uses ROS2 XML + implements external PD with kp=7.5**: Gains are wrong
(training used kp=5.0, kd=0.1) → different dynamics → robot may fall.

**Fix**: Use the training XML which has PD built into MuJoCo actuators. Set `ctrl` to
the target joint position (action_scale × policy_output + default_pos).

### 2. Contact Dimensionality (condim)

**Training XML**: Default geom `condim="3"` → 3D contact (normal + 2D sliding friction)
**ROS2 XML**: Default geom `condim="6"` → 6D contact (normal + 2D sliding + rolling + torsional friction)

condim=6 adds torsional and rolling friction that wasn't present during training.
This changes how feet interact with the ground significantly.

**Fix**: Use training XML (condim=3).

### 3. Collision Geometry Shape for Thighs

**Training XML**: Thigh collision = `type="sphere" size="0.025"` (simplified spherical collision)
**ROS2 XML**: Thigh collision = `type="cylinder" size="0.025 0.015"` (cylindrical collision)

Different shapes produce different contact points and forces when legs swing near the body.
The policy learned to walk with spherical thigh collisions.

**Fix**: Use training XML (sphere).

### 4. Solver Settings

**Training**: `cone="pyramidal" impratio="10" iterations="1" ls_iterations="5" eulerdamp="disable"`
**ROS2**: `cone="elliptic" impratio="100"` (defaults for iterations)

- Pyramidal vs elliptic friction cone: different friction force resolution
- iterations=1 vs default (100): much less accurate solver in training
- eulerdamp=disable: changes rotational damping behavior

**Fix**: Use training XML solver settings exactly.

## HIGH: Very likely to cause instability

### 5. Physics Timestep

**Training**: `timestep=0.004s` (4ms), environment_dt=0.02s (5 physics steps per policy step)
**ROS2**: `timestep=0.0001s` (0.1ms), control at 200Hz

Different timestep means different integration accuracy. The policy was trained at 4ms,
so using a finer timestep changes the contact and dynamics behavior.

**Fix**: Use timestep=0.004s, run 5 mj_step per policy inference (50Hz).

### 6. Joint Friction

**Training XML**: `damping="0.01" frictionloss="0.01"` (no explicit frictionloss difference)
**ROS2 non-backlash**: Same as training
**ROS2 backlash**: `frictionloss="0.125"` (12.5x higher!)

If using the backlash XML, joint friction is massively higher than training, causing
the policy's output to be insufficient to move joints properly.

**Fix**: Use training XML (no backlash, standard friction).

### 7. Observation History Rotation Logic

The observation vector maintains a history buffer. After each inference, the buffer is
rotated right by `kSingleObservationSize` (36) positions, and the newest observation
fills the first 36 slots. Getting this rotation direction wrong silently corrupts all
observations.

Training uses observation_history=4 → input is 144-dim (36×4). The ROS2 controller
allows configurable history. The standalone MUST read `observation_history` from the
policy JSON and use exactly the right total input size.

### 8. Projected Gravity Computation

The observation expects gravity projected into the body frame:
```
q_body_to_world = (w, x, y, z)
R_body_to_world = quaternion_to_matrix(q)
gravity_in_body = R_body_to_world^{-1} × (0, 0, -1)
```

MuJoCo's `framequat` sensor returns orientation as `(w, x, y, z)`. If the standalone
code uses a different quaternion convention (e.g., `(x, y, z, w)`), the gravity
projection will be completely wrong → policy receives garbage → falls.

## MEDIUM: Can cause gradual degradation

### 9. Action Scale and Default Position

Training uses `action_scale=0.75` and specific `default_joint_pos`. The policy JSON
may override these values. If the standalone hardcodes values that differ from what's
in the JSON, the commanded positions will be scaled incorrectly.

Also: the observation normalizes joint positions as `(q - default_pos)`. If default_pos
in the code doesn't match what was used during training, the observation is wrong.

### 10. Motor Dynamics (ROS2 only)

The ROS2 hardware interface models realistic motor dynamics:
- Bus voltage (24V), torque constant (kt=0.04 Nm/A), phase resistance (0.7Ω)
- Back-EMF limiting: max_current = (voltage - kt×velocity) / resistance
- Saturation torque (4.5 Nm), software torque limit (3.0 Nm)

Training does NOT have these motor dynamics (MuJoCo's built-in actuator with forcerange
±3 is simpler). So this is NOT an issue if using the training XML, but would be if trying
to replicate the ROS2 hardware interface.

### 11. Latency

Training simulates latency:
- Action latency: 20% chance of 0-step delay, 80% chance of 1-step delay
- IMU latency: 50/50 chance of 0 or 1 step delay

ROS2 can optionally add latency (command_latency_timesteps, imu_latency_timesteps, default 0).

No latency in standalone sim is probably fine (cleaner than training), but worth noting.

## LOW: Unlikely to cause falling but good to verify

### 12. Domain Randomization (training only)

Training randomizes: mass [0.9, 1.3], inertia [0.9, 1.3], friction [0.6, 1.4],
kp [0.6, 1.1], kd [0.8, 1.5], CoM shift, etc. Standalone uses fixed parameters.
Since the policy was trained with randomization, it should handle fixed parameters fine.

### 13. Observation Noise (training only)

Training adds noise: angular_velocity=0.1, gravity=0.05, motor_angle=0.05, last_action=0.01.
Standalone has no noise → cleaner observations → should help, not hurt.

### 14. Starting Height

Training starts at z ∈ [0.15, 0.20]. The XML's home keyframe has z=0.28.
Standalone should start at a reasonable standing height.

---

## Summary: What the Standalone Sim MUST Do

1. **Use `pupper_v3_complete.mjx.position.xml`** (training XML), NOT the ROS2 XML
2. **Let MuJoCo handle PD control** via built-in actuator model (gainprm/biasprm)
3. **Set ctrl = target position** (not torque)
4. **Match training timestep**: 0.004s physics, 5 steps per 50Hz policy inference
5. **Read all parameters from policy JSON**: observation_history, default_joint_pos, action_scale, joint limits, kp, kd
6. **Use correct quaternion convention**: MuJoCo framequat returns (w,x,y,z)
7. **Implement observation history rotation correctly**: rotate right, fill first slots
8. **Clip observations to [-100, 100]** and **clip actions to joint limits**
