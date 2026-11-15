"""Separate dense NumPy statevector candidate for high-support comparison."""
from __future__ import annotations
import math
import numpy as np


def evolve(qubits: int, gates):
    size = 1 << qubits
    state = np.zeros(size, dtype=np.complex128)
    state[0] = 1.0
    root2 = 1.0 / math.sqrt(2.0)
    for gate in gates:
        op = gate[0]
        if op in ("h", "rx", "ry"):
            q = gate[1]
            blocks = state.reshape((-1, 2, 1 << q))
            low, high = blocks[:, 0, :].copy(), blocks[:, 1, :].copy()
            if op == "h":
                blocks[:, 0, :] = (low + high) * root2
                blocks[:, 1, :] = (low - high) * root2
            else:
                angle = float(gate[2]) / 2.0
                cosine, sine = math.cos(angle), math.sin(angle)
                if op == "rx":
                    blocks[:, 0, :] = cosine * low - 1j * sine * high
                    blocks[:, 1, :] = cosine * high - 1j * sine * low
                else:
                    blocks[:, 0, :] = cosine * low - sine * high
                    blocks[:, 1, :] = sine * low + cosine * high
        elif op in ("rz", "z"):
            q = gate[1]
            blocks = state.reshape((-1, 2, 1 << q))
            angle = math.pi if op == "z" else float(gate[2])
            blocks[:, 0, :] *= np.exp(-0.5j * angle)
            blocks[:, 1, :] *= np.exp(0.5j * angle)
        elif op == "x":
            q = gate[1]
            blocks = state.reshape((-1, 2, 1 << q))
            low, high = blocks[:, 0, :].copy(), blocks[:, 1, :].copy()
            blocks[:, 0, :], blocks[:, 1, :] = high, low
        elif op == "cp":
            _, control, target, angle = gate
            tensor = state.reshape((2,) * qubits)
            selector = [slice(None)] * qubits
            selector[qubits - 1 - control] = 1
            selector[qubits - 1 - target] = 1
            tensor[tuple(selector)] *= np.exp(1j * float(angle))
        elif op == "cx":
            _, control, target = gate
            basis = np.arange(size, dtype=np.uint32)
            control_mask, target_mask = 1 << control, 1 << target
            low = basis[((basis & control_mask) != 0) & ((basis & target_mask) == 0)]
            tmp = state[low].copy()
            state[low] = state[low | target_mask]
            state[low | target_mask] = tmp
        else:
            raise ValueError(f"unsupported gate: {op}")
    return state