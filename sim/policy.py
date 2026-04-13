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

        # in_shape may be [None, 720] or [1, 720]
        self.input_size = [s for s in data["in_shape"] if s is not None][-1]
        # shape may be [None, N] or [N]
        last_shape = data["layers"][-1]["shape"]
        self.output_size = [s for s in last_shape if s is not None][-1]
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
