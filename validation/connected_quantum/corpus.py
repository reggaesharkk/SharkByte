"""Deterministic connected-circuit corpus for independent statevector checks."""
from __future__ import annotations

import hashlib
import json
import math
import random
from decimal import Decimal


WIDTHS = (2, 3, 4, 5, 6, 8, 10, 12, 14, 16)
ANALYTIC_WIDTHS = (20, 24, 30, 40)
REPLICATES_PER_WIDTH = 2
MASTER_SEED = 2026111600
RANDOM_LAYERS = 2


def _angle(rng: random.Random) -> float:
    magnitude = rng.randint(125_000, 3_100_000) / 1_000_000
    return magnitude if rng.getrandbits(1) else -magnitude


def angle_token(value: float) -> str:
    """Return a decimal-only round-trip token accepted by the source grammar."""
    return format(Decimal(repr(float(value))), "f")


def _connected_edges(width: int, rng: random.Random) -> list[tuple[int, int]]:
    order = list(range(width))
    rng.shuffle(order)
    edges = {tuple(sorted((order[i - 1], order[i])))
             for i in range(1, width)}
    candidates = [
        (a, b) for a in range(width) for b in range(a + 1, width)
        if (a, b) not in edges
    ]
    rng.shuffle(candidates)
    edges.update(candidates[: min(width // 4, len(candidates))])
    return sorted(edges)


def _inverse(gates: list[tuple]) -> list[tuple]:
    result = []
    for gate in reversed(gates):
        if gate[0] == "cp":
            result.append(("cp", gate[1], gate[2], -gate[3]))
        elif gate[0] in ("rx", "ry", "rz"):
            result.append((gate[0], gate[1], -gate[2]))
        else:
            result.append(gate)
    return result


def _render(name: str, width: int, seed: int, gates: list[tuple]) -> str:
    rows = [
        f"quantum {name} {{",
        f"  qubits {width};",
        "  shots 1;",
        f"  seed {seed};",
    ]
    for gate in gates:
        op = gate[0]
        if op in ("h", "x", "z"):
            rows.append(f"  {op} {gate[1]};")
        elif op == "cx":
            rows.append(f"  cx {gate[1]} {gate[2]};")
        elif op == "cp":
            rows.append(f"  cp {angle_token(gate[3])} {gate[1]} {gate[2]};")
        else:
            rows.append(f"  {op} {angle_token(gate[2])} {gate[1]};")
    rows.extend(("  measure_all;", "}"))
    return "\n".join(rows) + "\n"


def _case(name: str, width: int, seed: int, prefix: list[tuple],
          edges: list[tuple[int, int]], kind: str) -> dict:
    gates = prefix + _inverse(prefix)
    source = _render(name, width, seed, gates)
    if kind in ("random-connected", "adversarial-connected-low-support"):
        entanglement_expectation = "nonfactorizing-across-tested-cuts"
    elif kind == "adversarial-connected-but-separable":
        entanglement_expectation = "separable-product-control"
    else:
        entanglement_expectation = "record-without-required-classification"
    return {
        "id": name,
        "kind": kind,
        "entanglement_expectation": entanglement_expectation,
        "width": width,
        "seed": seed,
        "prefix_gate_count": len(prefix),
        "gates": [list(gate) for gate in gates],
        "entangling_edges": [list(edge) for edge in edges],
        "source": source,
        "source_sha256": hashlib.sha256(source.encode("utf-8")).hexdigest(),
    }


def _random_case(width: int, replicate: int) -> dict:
    seed = MASTER_SEED + width * 100 + replicate
    rng = random.Random(seed)
    gates: list[tuple] = []
    order = list(range(width))
    rng.shuffle(order)
    gates.extend(("h", q) for q in order)

    all_edges: set[tuple[int, int]] = set()
    local_axis = ("ry", "rz")
    for layer in range(RANDOM_LAYERS):
        qubit_order = list(range(width))
        rng.shuffle(qubit_order)
        axis = local_axis[layer]
        gates.extend((axis, q, _angle(rng)) for q in qubit_order)

        edges = _connected_edges(width, rng)
        all_edges.update(edges)
        rng.shuffle(edges)
        for a, b in edges:
            control, target = (a, b) if rng.getrandbits(1) else (b, a)
            gates.append(("cx", control, target))
            cp_control, cp_target = (
                (target, control) if rng.getrandbits(1) else (control, target)
            )
            gates.append(("cp", cp_control, cp_target, _angle(rng)))

        if layer == 1:
            gates.extend((("x", rng.randrange(width)), ("z", rng.randrange(width))))

    name = f"connected_{width:02d}q_seed_{seed}"
    return _case(name, width, seed, gates, sorted(all_edges), "random-connected")


def _adversarial_cases() -> list[dict]:
    width = 8
    chain = [(q, q + 1) for q in range(width - 1)]

    # The register interaction graph is a connected chain. The prefix includes
    # exact gate cancellations, controlled-phase sign cancellation, and
    # rotations at the accepted +/-4*pi boundary.
    cancellation = [("h", 0), ("h", 1)]
    cancellation.extend(("cx", a, b) for a, b in chain)
    cancellation.extend((
        ("cp", 0, 7, 0.8125),
        ("cp", 0, 7, -0.8125),
        ("cx", 3, 4),
        ("cx", 3, 4),
        ("rx", 2, 1.125),
        ("rx", 2, -1.125),
        ("ry", 0, 4 * math.pi),
        ("rz", 7, -4 * math.pi),
        ("cp", 1, 6, 4 * math.pi),
        ("h", 1),
        ("h", 1),
    ))
    first = _case(
        "adversarial_connected_cancellation_8q", width, 2026111691,
        cancellation, chain, "adversarial-cancellation-and-angle-boundaries",
    )

    # A global GHZ backbone over all eight qubits keeps only two occupied
    # amplitudes through a connected interaction graph. Non-Clifford phases
    # are then exactly undone in the full inverse.
    ghz = [("h", 0)]
    ghz.extend(("cx", q, q + 1) for q in range(width - 1))
    ghz.extend((
        ("cp", 0, 7, 0.73),
        ("cp", 2, 5, -1.1875),
        ("rz", 4, 0.625),
        ("rx", 3, 0.875),
    ))
    second = _case(
        "adversarial_connected_sparse_ghz_8q", width, 2026111692,
        ghz, chain, "adversarial-connected-low-support",
    )

    # Exercise the parser's exact 256-instruction ceiling with a fully
    # randomized two-qubit prefix and its inverse, including all supported
    # rotation families and non-Clifford interactions.
    rng = random.Random(2026111693)
    boundary = [("h", 0), ("cx", 0, 1)]
    axes = ("rx", "ry", "rz")
    for index in range(42):
        axis = axes[index % len(axes)]
        boundary.append((axis, index % 2, _angle(rng)))
        boundary.append(("cp", 0, 1, _angle(rng)))
        boundary.append(("cx", 0, 1) if index % 3 == 0 else ("z", index % 2))
    if len(boundary) != 128:
        raise AssertionError("gate-budget adversary must have a 128-gate prefix")
    third = _case(
        "adversarial_gate_budget_256_2q", 2, 2026111693,
        boundary, [(0, 1)], "adversarial-maximum-gate-budget",
    )

    # Connected gate support with no entanglement: each CNOT acts twice in
    # succession and every controlled phase has zero angle. Local H/RZ gates
    # therefore leave a tensor product even though the interaction graph is a
    # connected chain.
    product_width = 6
    product_edges = [(q, q + 1) for q in range(product_width - 1)]
    product = [("h", q) for q in range(product_width)]
    for control, target in product_edges:
        product.extend((("cx", control, target), ("cx", control, target)))
    product.extend(("cp", control, target, 0.0) for control, target in product_edges)
    product.extend(("rz", q, ((q + 1) / 16.0)) for q in range(product_width))
    fourth = _case(
        "adversarial_connected_but_separable_6q", product_width, 2026111694,
        product, product_edges, "adversarial-connected-but-separable",
    )
    return [first, second, third, fourth]


def build_cases() -> list[dict]:
    """Build the fixed 24-circuit corpus (20 randomized, four adversarial)."""
    cases = [
        _random_case(width, replicate)
        for width in WIDTHS
        for replicate in range(REPLICATES_PER_WIDTH)
    ]
    cases.extend(_adversarial_cases())
    return cases


def build_sparse_analytic_cases() -> list[dict]:
    """Build globally connected GHZ circuits with a closed-form exact oracle."""
    cases = []
    controlled_phases = (0.375, -0.625, 0.8125, -1.1875)
    for width in ANALYTIC_WIDTHS:
        prefix: list[tuple] = [("h", 0)]
        prefix.extend(("cx", q, q + 1) for q in range(width - 1))
        phase_edges = (
            (0, width - 1),
            (width // 4, (3 * width) // 4),
            (1, width // 2),
            (width // 3, width - 2),
        )
        prefix.extend(
            ("cp", control, target, angle)
            for (control, target), angle in zip(phase_edges, controlled_phases)
        )
        rz_angles = [
            (((q % 9) + 1) / 32.0) * (1.0 if q % 2 == 0 else -1.0)
            for q in range(width)
        ]
        prefix.extend(("rz", q, angle) for q, angle in enumerate(rz_angles))
        phase_gates = len(prefix)
        prefix.extend(("cx", q, q + 1) for q in reversed(range(width - 1)))
        prefix.append(("h", 0))
        source = _render(f"connected_ghz_analytic_{width}q", width, 2026111700 + width, prefix)
        cases.append({
            "id": f"connected_ghz_analytic_{width}q",
            "kind": "connected-ghz-closed-form",
            "width": width,
            "seed": 2026111700 + width,
            "prefix_gate_count": len(prefix),
            "entangled_ghz_gate_count": phase_gates,
            "gates": [list(gate) for gate in prefix],
            "entangling_edges": [
                [q, q + 1] for q in range(width - 1)
            ] + [list(edge) for edge in phase_edges],
            "controlled_phase_angles": list(controlled_phases),
            "rz_angles": rz_angles,
            "source": source,
            "source_sha256": hashlib.sha256(source.encode("utf-8")).hexdigest(),
            "exact_relative_phase": math.fsum(controlled_phases) + math.fsum(rz_angles),
            "reference_method": "GHZ branch phase accumulation, inverse CNOT chain, final H projection",
        })
    return cases


def analytic_ghz_state(case: dict) -> dict[int, complex]:
    """Exact amplitudes after the connected GHZ circuit's final H projection."""
    phase = complex(math.cos(case["exact_relative_phase"]),
                    math.sin(case["exact_relative_phase"]))
    common = complex(
        math.cos(-math.fsum(case["rz_angles"]) / 2),
        math.sin(-math.fsum(case["rz_angles"]) / 2),
    )
    return {
        0: common * (1.0 + phase) / 2.0,
        1: common * (1.0 - phase) / 2.0,
    }


def analytic_entangled_ghz_state(case: dict) -> dict[int, complex]:
    """Exact phase-GHZ state before the inverse CNOT chain and final H."""
    relative_phase = complex(
        math.cos(case["exact_relative_phase"]),
        math.sin(case["exact_relative_phase"]),
    )
    rz_sum = math.fsum(case["rz_angles"])
    common = complex(math.cos(-rz_sum / 2), math.sin(-rz_sum / 2))
    normalization = 1.0 / math.sqrt(2.0)
    return {
        0: common * normalization,
        (1 << case["width"]) - 1: common * relative_phase * normalization,
    }


def graph_is_connected(width: int, edges: list[list[int]] | list[tuple[int, int]]) -> bool:
    if width <= 1:
        return True
    adjacency = [set() for _ in range(width)]
    for a, b in edges:
        adjacency[a].add(b)
        adjacency[b].add(a)
    reached = {0}
    frontier = [0]
    while frontier:
        current = frontier.pop()
        for neighbour in adjacency[current] - reached:
            reached.add(neighbour)
            frontier.append(neighbour)
    return len(reached) == width


def corpus_sha256(cases: list[dict] | None = None) -> str:
    if cases is None:
        cases = build_cases()
    body = [
        {"id": case["id"], "source_sha256": case["source_sha256"]}
        for case in cases
    ]
    raw = json.dumps(body, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()
