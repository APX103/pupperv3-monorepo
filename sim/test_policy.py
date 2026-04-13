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
