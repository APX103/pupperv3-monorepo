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
