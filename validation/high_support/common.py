"""Deterministic high-support connected-circuit corpus and independent oracles."""
from __future__ import annotations

from decimal import Decimal
import hashlib
import json
import math
import random

WIDTHS = (17, 18, 20)
MASTER_SEED = 2026111600
SUPPORTED = {"h", "x", "z", "cx", "cp", "rx", "ry", "rz"}


def sha256(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def canonical_json(value) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")


def gate_descriptors(gates):
    result = []
    for gate in gates:
        op = gate[0]
        if op in ("h", "x", "z"):
            result.append({"op": op, "qubits": [gate[1]]})
        elif op == "cx":
            result.append({"op": op, "qubits": [gate[1], gate[2]]})
        elif op == "cp":
            result.append({"op": op, "qubits": [gate[1], gate[2]], "angle": float(gate[3])})
        elif op in ("rx", "ry", "rz"):
            result.append({"op": op, "qubits": [gate[1]], "angle": float(gate[2])})
        else:
            raise ValueError(f"unsupported gate {op}")
    return result


def generate_plan(width: int, case: str = "entangled") -> dict:
    if case not in ("entangled", "random_connected", "connected_separable", "numerical_adversary", "roundtrip"):
        raise ValueError("unsupported high-support case")
    if case == "roundtrip":
        if width not in WIDTHS:
            raise ValueError(f"roundtrip widths are {WIDTHS}")
        forward = generate_plan(width, "entangled")
        backwards = []
        for gate in reversed(forward["gates"]):
            op = gate[0]
            if op == "cp":
                backwards.append(["cp", gate[1], gate[2], -float(gate[3])])
            elif op in ("rx", "ry", "rz"):
                backwards.append([op, gate[1], -float(gate[2])])
            else:
                backwards.append(list(gate))
        result = dict(forward)
        result["case"] = case
        result["forward_gate_count"] = len(forward["gates"])
        result["gates"] = forward["gates"] + backwards
        result["cross_cut_cp"] = []
        result["gate_sequence_sha256"] = sha256(canonical_json(gate_descriptors(result["gates"])))
        return result
    if case in ("entangled", "random_connected") and width not in WIDTHS:
        raise ValueError(f"entangled widths are {WIDTHS}")
    if case == "connected_separable" and width != 20:
        raise ValueError("connected_separable control is fixed at 20 qubits")
    if case == "numerical_adversary" and width != 17:
        raise ValueError("numerical_adversary is fixed at 17 qubits")
    if not 2 <= width <= 40:
        raise ValueError("width must be in 2..40")
    seed = MASTER_SEED + width
    gates = [("h", q) for q in range(width)]
    cross_edges = []
    split = width // 2
    topology = "connected_cnot_chain_separable_control"
    if case == "connected_separable":
        gates.extend(("cx", q, q + 1) for q in range(width - 1))
    elif case == "numerical_adversary":
        topology = "connected_chain_of_near_4pi_controlled_phase_inverse_pairs"
        limit = 4.0 * math.pi
        near = limit - 1e-12
        for q in range(width - 1):
            gates.extend((("cp", q, q + 1, near), ("cp", q, q + 1, -near)))
        gates.extend((("cp", 0, width - 1, limit), ("cp", 0, width - 1, -limit)))
        for q in range(width):
            op = ("rx", "ry", "rz")[q % 3]
            gates.extend(((op, q, near), (op, q, -near)))
    elif case == "entangled":
        rng = random.Random(seed)
        topology = "complete_bipartite_controlled_phase_with_partition_chains"
        for left in range(split):
            for right in range(split, width):
                angle = rng.uniform(0.19, 2.83)
                cross_edges.append((left, right, angle))
                gates.append(("cp", left, right, angle))
        for begin, end in ((0, split), (split, width)):
            for q in range(begin, end - 1):
                gates.append(("cx", q, q + 1))
        for q, op in ((0, "ry"), (split, "rx"), (width - 1, "rz")):
            gates.append((op, q, rng.uniform(-2.4, 2.4)))
    else:
        rng = random.Random(seed)
        topology = "seeded_erdos_renyi_bipartite_phase_edges_with_random_partition_trees"
        edge_probability = 0.68
        pairs = [(left, right) for left in range(split) for right in range(split, width)
                 if rng.random() < edge_probability]
        if not pairs:
            pairs.append((rng.randrange(split), rng.randrange(split, width)))
        for left, right in pairs:
            angle = rng.uniform(0.19, 2.83)
            cross_edges.append((left, right, angle))
            gates.append(("cp", left, right, angle))
        for begin, end in ((0, split), (split, width)):
            for q in range(begin + 1, end):
                parent = rng.randrange(begin, q)
                gates.append(("cx", parent, q))
        for q, op in ((0, "ry"), (split, "rx"), (width - 1, "rz")):
            gates.append((op, q, rng.uniform(-2.4, 2.4)))
    body = {"case": case, "qubits": width, "seed": seed, "topology_seed": seed,
            "topology_kind": topology, "split": split, "gates": [list(g) for g in gates],
            "two_qubit_edge_count": sum(1 for gate in gates if gate[0] in ("cx", "cp")),
            "gate_sequence_sha256": sha256(canonical_json(gate_descriptors(gates))),
            "cross_cut_cp": [[a, b, angle] for a, b, angle in cross_edges]}
    return body

def render_source(plan: dict) -> bytes:
    width = plan["qubits"]
    lines = [f"quantum high_support_{plan['case']}_{width}q {{",
             f"    qubits {width};", "    shots 1;", f"    seed {plan['seed']};"]
    for gate in plan["gates"]:
        op = gate[0]
        if op in ("h", "x", "z"):
            lines.append(f"    {op} {gate[1]};")
        elif op == "cx":
            lines.append(f"    cx {gate[1]} {gate[2]};")
        elif op == "cp":
            angle = format(Decimal(repr(float(gate[3]))), "f")
            lines.append(f"    cp {angle} {gate[1]} {gate[2]};")
        else:
            angle = format(Decimal(repr(float(gate[2]))), "f")
            lines.append(f"    {op} {angle} {gate[1]};")
    lines.extend(("    measure_all;", "}"))
    return ("\n".join(lines) + "\n").encode("utf-8")


def inverse_plan(plan: dict) -> dict:
    inverse = []
    for gate in reversed(plan["gates"]):
        op = gate[0]
        if op == "cp":
            inverse.append(["cp", gate[1], gate[2], -float(gate[3])])
        elif op in ("rx", "ry", "rz"):
            inverse.append([op, gate[1], -float(gate[2])])
        else:
            inverse.append(list(gate))
    result = dict(plan)
    result["case"] = plan["case"] + "_forward_inverse"
    result["gates"] = inverse
    result["gate_sequence_sha256"] = sha256(canonical_json(gate_descriptors(inverse)))
    result["cross_cut_cp"] = []
    return result


def is_two_qubit_graph_connected(plan: dict) -> bool:
    width = plan["qubits"]
    parent = list(range(width))
    def find(q):
        while parent[q] != q:
            parent[q] = parent[parent[q]]
            q = parent[q]
        return q
    for gate in plan["gates"]:
        if gate[0] in ("cx", "cp"):
            a, b = find(gate[1]), find(gate[2])
            parent[a] = b
    return len({find(q) for q in range(width)}) == 1


def analytic_phase_matrix(plan: dict):
    import numpy as np
    width, split = plan["qubits"], plan["split"]
    rows = np.arange(1 << split, dtype=np.uint32)[:, None]
    cols = np.arange(1 << (width - split), dtype=np.uint32)[None, :]
    phase = np.zeros((1 << split, 1 << (width - split)), dtype=np.float64)
    for left, right, angle in plan["cross_cut_cp"]:
        mask = (((rows >> left) & 1) != 0) & (((cols >> (right - split)) & 1) != 0)
        phase[mask] += angle
    return np.exp(1j * phase) / math.sqrt(1 << width)


def entanglement_metrics(state, width: int, split: int, *, relative_cutoff: float = 1e-10) -> dict:
    import numpy as np
    matrix = np.asarray(state, dtype=np.complex128).reshape((1 << (width - split), 1 << split)).T
    singular = np.linalg.svd(matrix, compute_uv=False)
    weights = singular * singular
    total = float(weights.sum())
    if total <= 0 or not math.isfinite(total):
        raise ArithmeticError("invalid Schmidt spectrum")
    weights /= total
    positive = weights[weights > 0]
    entropy = float(-np.sum(positive * np.log2(positive)))
    rank = int(np.count_nonzero(singular > (singular[0] * relative_cutoff)))
    return {"schmidt_rank_at_relative_cutoff": rank,
            "relative_singular_value_cutoff": relative_cutoff,
            "von_neumann_entropy_bits": entropy,
            "maximum_entropy_bits": float(min(split, width - split)),
            "entropy_fraction_of_maximum": entropy / min(split, width - split),
            "purity": float(np.sum(weights * weights)),
            "singular_values": singular.tolist(),
            "normalization": total}