"""Reproduce moving-branch protection mappings and measure opt-in overhead."""
import copy
import hashlib
import json
import platform
import random
import statistics
import subprocess
import sys
import time
import tracemalloc
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from benchmarks.sb_quantum_benchmark.bounded_support import simulate
from benchmarks.sb_quantum_benchmark.certified_support import certify, verify
from benchmarks.sb_quantum_benchmark.sparse_backend import Circuit


TRACKED = (
    "benchmarks/sb_quantum_benchmark/bounded_support.py",
    "benchmarks/sb_quantum_benchmark/certified_support.py",
    "benchmarks/sb_quantum_benchmark/verify_bounded.py",
    "tests/test_certified_support.py",
    "tools/high_support/check_moving_branch_protection.py",
    "tools/high_support/check_platform_regressions.py",
    "docs/certified-bounded-support.md",
    "docs/bounded-support.md",
    "docs/bounded-support-audit.md",
    "CLAIM_BOUNDARIES.md",
    "REPRODUCIBILITY.md",
    "README.md",
    ".github/workflows/certified-support.yml",
)


def sha(data):
    return hashlib.sha256(data).hexdigest()


def revision():
    return subprocess.check_output(["git", "-C", str(ROOT), "rev-parse", "HEAD"],
                                   text=True).strip()


def expected_position(origin, gates):
    basis = origin
    for gate in gates:
        if gate[0] == "x":
            basis ^= 1 << gate[1]
        elif gate[0] == "cx" and basis & (1 << gate[1]):
            basis ^= 1 << gate[2]
    return basis


def archived_case():
    circuit = Circuit(4, (("x", 0),), "archived-moving-protected-branch")
    initial = {2: 1+0j, 1: complex(1e-7, 0)}
    common = dict(support_cap=8, memory_budget_bytes=16384)
    fixed = certify(circuit, initial, "1e-6", protected=(1,), **common)
    moving = certify(circuit, initial, "1e-6", protected_branches=(1,), **common)
    if fixed["status"] != "PASS" or 0 in fixed["state"]:
        raise AssertionError("archived fixed-index control changed unexpectedly")
    if moving["status"] != "PASS" or 0 not in moving["state"]:
        raise AssertionError("moving branch was not retained at its permuted coordinate")
    checked = verify(circuit, initial, moving["state"], moving["certificate"], "1e-6",
                     protected_branches=(1,))
    if checked["status"] != "PASS":
        raise AssertionError(checked)
    return dict(fixed_mode=dict(status=fixed["status"], final_support=len(fixed["state"]),
                                deleted=[item for e in fixed["certificate"]["ledger"]["events"]
                                         for item in e["removed"]]),
                moving_mode=dict(status=moving["status"], final_support=len(moving["state"]),
                                 final_positions=moving["certificate"]["ledger"][
                                     "final_protected_positions"],
                                 verifier_status=checked["status"],
                                 exact_squared_error=checked["exact_squared_error"]))


def exhaustive_single_gate_maps():
    checked = 0
    for width in range(1, 5):
        gates = [("x", q) for q in range(width)]
        gates += [("z", q) for q in range(width)]
        gates += [("cx", c, t) for c in range(width) for t in range(width) if c != t]
        for gate in gates:
            for origin in range(1 << width):
                initial = {origin: complex(0.25, -0.125)}
                circuit = Circuit(width, (gate,), "exhaustive-moving-map")
                result = certify(circuit, initial, "1e-8", support_cap=1 << width,
                                 memory_budget_bytes=(1 << width)*2048,
                                 protected_branches=(origin,))
                position = expected_position(origin, (gate,))
                expected_amplitude = initial[origin]
                if gate[0] == "z" and origin & (1 << gate[1]):
                    expected_amplitude = -expected_amplitude
                if (result["status"] != "PASS" or result["state"] != {position: expected_amplitude}
                        or result["certificate"]["ledger"]["final_protected_positions"]
                        != [[origin, position]]):
                    raise AssertionError((width, gate, origin, result))
                checked += 1
    return dict(widths=[1, 2, 3, 4], individual_gate_origin_mappings=checked,
                families=["x", "z", "cx"], exhaustive_over_each_legal_single_gate_and_basis_origin=True)


def randomized_circuits():
    rows = []
    for width, seed in ((5, 17), (8, 29), (12, 43), (20, 71)):
        rng = random.Random(width*1000+seed)
        gates = []
        for _ in range(250):
            op = rng.choice(("x", "z", "cx"))
            if op == "cx":
                gates.append((op, *rng.sample(range(width), 2)))
            else:
                gates.append((op, rng.randrange(width)))
        origins = (0, 1, (1 << width)-1)
        initial = {0: 0.75+0.25j, 1: complex(1e-7, -2e-7),
                   2: complex(1e-5, 0), (1 << width)-1: complex(3e-7, 0)}
        circuit = Circuit(width, tuple(gates), "random-moving-map")
        result = certify(circuit, initial, "1e-3", support_cap=8,
                         memory_budget_bytes=8*4096, interval=7,
                         protected_branches=origins)
        if result["status"] != "PASS":
            raise AssertionError((width, seed, result))
        checked = verify(circuit, initial, result["state"], result["certificate"],
                         "1e-3", protected_branches=origins)
        if checked["status"] != "PASS":
            raise AssertionError((width, seed, checked))
        final = [[origin, expected_position(origin, gates)] for origin in origins]
        actual = result["certificate"]["ledger"]["final_protected_positions"]
        if actual != final:
            raise AssertionError((width, seed, actual, final))
        if not result["certificate"]["ledger"]["events"]:
            raise AssertionError("randomized control did not exercise any compaction event")
        rows.append(dict(width=width, seed=seed, gates=len(gates),
                         gate_sha256=sha(json.dumps(gates, separators=(",", ":")).encode()),
                         origins=list(origins), final_positions=actual,
                         events=len(result["certificate"]["ledger"]["events"]),
                         deleted_coordinates=sum(len(e["removed"])
                                                for e in result["certificate"]["ledger"]["events"]),
                         exact_squared_error=checked["exact_squared_error"],
                         certified_l2_bound=checked["certified_l2_bound"]))
    return rows


def adversarial_replay_checks():
    circuit = Circuit(4, (("x", 0), ("cx", 0, 2), ("z", 2)), "forgery-control")
    initial = {2: 1+0j, 1: complex(1e-7, 0), 4: complex(2e-7, 0)}
    result = certify(circuit, initial, "1e-6", support_cap=8,
                     memory_budget_bytes=16384, protected_branches=(1,))
    cert = result["certificate"]
    mutations = {
        "wrong-final-map": lambda c: c["ledger"]["final_protected_positions"][0].__setitem__(1, 6),
        "wrong-origin": lambda c: c["ledger"]["protected_branches"].__setitem__(0, 0),
        "wrong-policy": lambda c: c["ledger"].__setitem__("protection_mode", "fixed"),
    }
    rejected = []
    for name, mutate in mutations.items():
        forged = copy.deepcopy(cert)
        mutate(forged)
        answer = verify(circuit, initial, result["state"], forged, "1e-6")
        if answer["status"] != "FAIL":
            raise AssertionError((name, answer))
        rejected.append(name)
    if not cert["ledger"]["events"]:
        raise AssertionError("forgery control needs a deletion event")
    forged = copy.deepcopy(cert)
    current = 0  # origin 1 -> X(0): 0; the next CX is inactive on this branch
    original = forged["ledger"]["events"][0]["removed"][0]
    forged["ledger"]["events"][0]["removed"][0] = [current, *original[1:]]
    answer = verify(circuit, initial, result["state"], forged, "1e-6")
    if answer["status"] != "FAIL":
        raise AssertionError(("deleting-current-protected-coordinate", answer))
    rejected.append("deleting-current-protected-coordinate")
    unsupported_circuit = Circuit(2, (("h", 0),), "mixing-rejected")
    unsupported = certify(unsupported_circuit, {0: 1+0j}, "1e-8", support_cap=4,
                          memory_budget_bytes=8192, protected_branches=(0,))
    if unsupported.get("status") != "UNSUPPORTED":
        raise AssertionError(unsupported)
    return dict(forged_certificates_rejected=rejected,
                mixing_gate_status=unsupported["status"], mixing_gate_reason=unsupported["reason"])


def overhead_benchmark():
    width = 10
    rng = random.Random(41019)
    gates = []
    for _ in range(1200):
        op = rng.choice(("x", "z", "cx"))
        if op == "cx":
            gates.append((op, *rng.sample(range(width), 2)))
        else:
            gates.append((op, rng.randrange(width)))
    circuit = Circuit(width, tuple(gates), "moving-protection-overhead")
    origins = tuple(range(1, 33))
    initial = {0: 1+0j, **{origin: complex(1e-6 + origin*1e-10, 0)
                            for origin in origins}}
    kwargs = dict(support_cap=64, memory_budget_bytes=64*2048, interval=1)
    samples = {"fixed": [], "moving": []}
    peaks = {"fixed": [], "moving": []}
    receipt_bytes = {}

    def run(label):
        tracemalloc.start()
        started = time.perf_counter()
        if label == "fixed":
            state, ledger = simulate(circuit, "1e-20", initial_state=initial,
                                     protected=origins, **kwargs)
        else:
            state, ledger = simulate(circuit, "1e-20", initial_state=initial,
                                     protected_branches=origins, **kwargs)
        elapsed = time.perf_counter()-started
        _, peak = tracemalloc.get_traced_memory()
        tracemalloc.stop()
        samples[label].append(elapsed)
        peaks[label].append(peak)
        receipt_bytes[label] = len(json.dumps(ledger, separators=(",", ":")).encode())
        if len(state) != len(initial):
            raise AssertionError("tiny-budget benchmark unexpectedly deleted support")
    for label in ("fixed", "moving"):
        run(label)  # warm-up, excluded below
        samples[label].clear()
        peaks[label].clear()
    for sample in range(7):
        order = ("fixed", "moving") if sample % 2 == 0 else ("moving", "fixed")
        for label in order:
            run(label)
    medians = {label: statistics.median(values) for label, values in samples.items()}
    trace_medians = {label: int(statistics.median(values)) for label, values in peaks.items()}
    return dict(width=width, gates=len(gates), initial_support=len(initial), branch_count=len(origins),
                samples=7, wall_seconds_median=medians,
                moving_to_fixed_wall_ratio=medians["moving"]/medians["fixed"],
                traced_peak_bytes_median=trace_medians,
                moving_to_fixed_traced_peak_ratio=(trace_medians["moving"] /
                                                   max(1, trace_medians["fixed"])),
                ledger_json_bytes=receipt_bytes,
                moving_to_fixed_ledger_size_delta_bytes=receipt_bytes["moving"]-receipt_bytes["fixed"],
                notes="Single local CPython sample set; tracemalloc is not process RSS; no speedup claim.")


def main():
    archive = archived_case()
    exhaustive = exhaustive_single_gate_maps()
    randomized = randomized_circuits()
    adversarial = adversarial_replay_checks()
    overhead = overhead_benchmark()
    record = dict(
        schema="sharkbyte/moving-branch-protection-evidence-v1",
        implementation_commit=revision(),
        python=sys.version,
        platform=platform.platform(),
        architecture=platform.machine(),
        source_hashes={path: sha((ROOT/path).read_bytes()) for path in TRACKED},
        archived_counterexample=archive,
        exhaustive_mappings=exhaustive,
        randomized_signed_permutation_circuits=randomized,
        adversarial_replay=adversarial,
        opt_in_overhead=overhead,
        decisions={
            "archived_counterexample_repaired_in_moving_mode": "PASS",
            "fixed_index_mode_preserved": "PASS",
            "single_gate_mappings_all_origins_through_four_qubits": "PASS",
            "randomized_larger_circuits_exactly_replayed": "PASS",
            "mixing_gates_rejected": "PASS",
            "performance_generalization": "OPEN",
            "moving_protection_through_mixing_gates": "UNSUPPORTED",
        },
        reproducible_command="python tools/high_support/check_moving_branch_protection.py > <evidence.json>",
    )
    print(json.dumps(record, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
