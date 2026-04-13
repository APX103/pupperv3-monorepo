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
