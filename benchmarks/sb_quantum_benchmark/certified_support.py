"""Certified support pruning for signed basis permutations only.

Reference amplitudes are exact binary64 inputs. Supported gates only permute
coordinates and flip signs, so they perform no rounded coefficient mixing.
"""
from fractions import Fraction
import hashlib
import json
import math
import platform
import sys
import time

from .bounded_support import (MOVING_BRANCH_MODE, TICKS,
                              simulate as compact_simulate)
from .sparse_backend import Circuit, MAX_WALL_SECONDS, validate

SEMANTICS = "binary64-input/signed-permutation/canonical-unnormalized-v1"
TRACKED_SEMANTICS = SEMANTICS + "/moving-initial-basis-branches-v1"
ROOT_PRECISION = 1200
ROOT_SCALE = 1 << ROOT_PRECISION
SUPPORTED = frozenset(("x", "z", "cx"))


def _environment_reason():
    if sys.implementation.name != "cpython":
        return "requires CPython complex values"
    if (sys.float_info.radix, sys.float_info.mant_dig, sys.float_info.max_exp) != (2, 53, 1024):
        return "requires IEEE-754 binary64 components"
    if sys.byteorder not in ("little", "big"):
        return "unsupported byte order"
    return None


def _rational_budget(value):
    if isinstance(value, Fraction):
        budget = value
    elif isinstance(value, str):
        budget = Fraction(value)
    else:
        raise TypeError("budget must be a decimal or rational string")
    if not 0 < budget < 1:
        raise ValueError("budget must be between zero and one")
    return budget


def _normalized_gates(circuit):
    gates = []
    for index, gate in enumerate(circuit.gates):
        op = gate[0].lower()
        if op not in SUPPORTED:
            return None, f"gate {index} ({op}) is outside the certified signed-permutation subset"
        gates.append((op, *gate[1:]))
    return tuple(gates), None


def _input_state(initial_state, qubits):
    if not isinstance(initial_state, dict) or not initial_state:
        raise ValueError("initial_state must be a nonempty basis-to-complex dictionary")
    state = {}
    for basis, value in initial_state.items():
        if type(basis) is not int or not 0 <= basis < (1 << qubits):
            raise ValueError("initial basis is outside the register")
        if not isinstance(value, complex):
            raise ValueError("initial amplitudes must be Python complex values")
        real, imag = float(value.real), float(value.imag)
        if not math.isfinite(real) or not math.isfinite(imag):
            raise ValueError("initial amplitudes must be finite")
        value = complex(real, imag)
        if value != 0j:
            state[basis] = value
    if not state:
        raise ValueError("initial state must have nonzero norm")
    return state


def _branch_origins(origins, qubits):
    try:
        values = tuple(origins)
    except TypeError as exc:
        raise ValueError("protected_branches must be an iterable of basis indices") from exc
    if (any(type(i) is not int or not 0 <= i < (1 << qubits) for i in values)
            or len(values) != len(set(values))):
        raise ValueError("invalid or duplicate protected branch origin")
    return tuple(sorted(values))


def _float_fraction(value):
    numerator, denominator = value.as_integer_ratio()
    return Fraction(numerator, denominator)


def _state_digest(state):
    payload = [[basis, value.real.hex(), value.imag.hex()]
               for basis, value in sorted(state.items())]
    return hashlib.sha256(json.dumps(payload, separators=(",", ":")).encode()).hexdigest()


def _circuit_digest(circuit, gates):
    payload = dict(qubits=circuit.qubits, gates=gates)
    return hashlib.sha256(json.dumps(payload, separators=(",", ":")).encode()).hexdigest()


def _fraction_state(state):
    return {basis: (_float_fraction(value.real), _float_fraction(value.imag))
            for basis, value in state.items()}


def _gate_exact(state, gate):
    op = gate[0]
    if op == "x":
        bit = 1 << gate[1]
        return {basis ^ bit: value for basis, value in state.items()}
    if op == "cx":
        control, target = gate[1], gate[2]
        control_bit, target_bit = 1 << control, 1 << target
        return {basis ^ target_bit if basis & control_bit else basis: value
                for basis, value in state.items()}
    bit = 1 << gate[1]
    return {basis: ((-value[0], -value[1]) if basis & bit else value)
            for basis, value in state.items()}


def _move_branch_positions(positions, gate, deadline=float("inf")):
    """Propagate initial-coordinate identities through an exact signed permutation."""
    op = gate[0]
    bit = 1 << gate[1] if op in ("x", "z") else None
    control = (1 << gate[1]) if op == "cx" else None
    target = (1 << gate[2]) if op == "cx" else None
    if op not in ("x", "z", "cx"):
        raise ValueError(f"moving-branch protection does not support gate {op}")
    for index, origin in enumerate(positions):
        if index % 256 == 0 and time.monotonic() >= deadline:
            raise ValueError("moving-branch verification deadline exceeded")
        basis = positions[origin]
        if op == "x":
            positions[origin] = basis ^ bit
        elif op == "cx" and basis & control:
            positions[origin] = basis ^ target
    return positions


def _ceil_sqrt_fraction(value, scale):
    """Smallest integer k such that k/scale >= sqrt(value), exactly."""
    if value < 0:
        raise ValueError("square root argument must be nonnegative")
    scaled_numerator = value.numerator * scale * scale
    denominator = value.denominator
    floor_root = math.isqrt(scaled_numerator // denominator)
    if floor_root * floor_root * denominator == scaled_numerator:
        return floor_root
    return floor_root + 1


def _root_interval(value):
    lower = math.isqrt(value.numerator * ROOT_SCALE * ROOT_SCALE // value.denominator)
    if lower * lower * value.denominator == value.numerator * ROOT_SCALE * ROOT_SCALE:
        upper = lower
    else:
        upper = lower + 1
    return dict(scale=str(ROOT_SCALE), lower=str(lower), upper=str(upper),
                width_numerator=str(upper-lower))


def _decode_witness(real_hex, imag_hex):
    if not isinstance(real_hex, str) or not isinstance(imag_hex, str):
        raise ValueError("witness components must be hexadecimal strings")
    try:
        real, imag = float.fromhex(real_hex), float.fromhex(imag_hex)
    except (ValueError, OverflowError) as exc:
        raise ValueError("malformed hexadecimal amplitude") from exc
    if not math.isfinite(real) or not math.isfinite(imag):
        raise ValueError("non-finite witness amplitude")
    if real.hex() != real_hex or imag.hex() != imag_hex:
        raise ValueError("witness amplitude is not canonical float.hex")
    return _float_fraction(real), _float_fraction(imag)


def certify(circuit, initial_state, budget, *, support_cap, memory_budget_bytes,
            max_seconds=30, interval=1, protected=(), normalize=False,
            protected_branches=None):
    """Return PASS plus a deletion certificate, or explicit UNSUPPORTED."""
    environment = _environment_reason()
    if environment:
        return dict(status="UNSUPPORTED", reason=environment)
    if normalize:
        return dict(status="UNSUPPORTED",
                    reason="renormalized outputs are outside this exact subset")
    validate(circuit, support_cap=support_cap, memory_budget_bytes=memory_budget_bytes)
    gates, reason = _normalized_gates(circuit)
    if reason:
        return dict(status="UNSUPPORTED", reason=reason)
    budget = _rational_budget(budget)
    initial = _input_state(initial_state, circuit.qubits)
    tracking = protected_branches is not None
    if tracking and protected:
        raise ValueError("fixed and moving-branch protection cannot be combined")
    branch_origins = _branch_origins(protected_branches, circuit.qubits) if tracking else None
    if tracking and any(origin not in initial for origin in branch_origins):
        raise ValueError("each protected branch origin must have a nonzero initial amplitude")
    state, ledger = compact_simulate(
        Circuit(circuit.qubits, gates, circuit.name), str(budget),
        support_cap=support_cap, memory_budget_bytes=memory_budget_bytes,
        max_seconds=max_seconds, interval=interval, protected=protected,
        initial_state=dict(initial), protected_branches=branch_origins,
    )
    bound = Fraction(ledger["charged_l2"])
    certificate = dict(
        semantics=TRACKED_SEMANTICS if tracking else SEMANTICS,
        circuit_sha256=_circuit_digest(circuit, gates),
        initial_state_sha256=_state_digest(initial),
        requested_budget=str(budget),
        error_components=dict(
            coefficient_evaluation="0",
            complex_gate_arithmetic="0",
            accumulated_gate_error="0",
            amplitude_deletion=str(bound),
            renormalization="0",
            total=str(bound),
        ),
        root_interval_bits=ROOT_PRECISION,
        ledger=ledger,
    )
    verification = verify(circuit, initial, state, certificate, budget,
                          protected_branches=branch_origins if tracking else None)
    if verification["status"] != "PASS":
        raise ArithmeticError("self-verification of exact-subset certificate failed")
    return dict(status="PASS", state=state, certificate=certificate,
                verification=verification)


def verify(circuit, initial_state, output_state, certificate, budget,
           *, protected_branches=None, max_seconds=30):
    """Verify with an exact Fraction signed-permutation oracle, independent of evolve."""
    environment = _environment_reason()
    if environment:
        return dict(status="UNSUPPORTED", reason=environment)
    try:
        semantics = certificate.get("semantics")
        if semantics not in (SEMANTICS, TRACKED_SEMANTICS):
            raise ValueError("unknown mathematical semantics")
        tracking = semantics == TRACKED_SEMANTICS
        if tracking and (not 0 < max_seconds <= MAX_WALL_SECONDS):
            raise ValueError("invalid moving-branch verification deadline")
        deadline = time.monotonic() + max_seconds if tracking else float("inf")
        budget = _rational_budget(budget)
        initial = _input_state(initial_state, circuit.qubits)
        cap = max(1, len(initial))
        validate(circuit, support_cap=cap, memory_budget_bytes=cap*512)
        gates, reason = _normalized_gates(circuit)
        if reason:
            return dict(status="UNSUPPORTED", reason=reason)
        if certificate.get("requested_budget") != str(budget):
            raise ValueError("requested budget mismatch")
        if certificate.get("initial_state_sha256") != _state_digest(initial):
            raise ValueError("initial state digest mismatch")
        if certificate.get("circuit_sha256") != _circuit_digest(circuit, gates):
            raise ValueError("circuit digest mismatch")
        components = certificate.get("error_components")
        if not isinstance(components, dict):
            raise ValueError("missing error component ledger")
        for name in ("coefficient_evaluation", "complex_gate_arithmetic",
                     "accumulated_gate_error", "renormalization"):
            if Fraction(components[name]) != 0:
                raise ValueError(f"unsupported nonzero {name}")
        ledger = certificate["ledger"]
        ticks = ledger["ticks_per_budget"]
        if type(ticks) is not int or ticks != TICKS:
            raise ValueError("unknown ledger tick scale")
        interval = ledger["interval"]
        if type(interval) is not int or interval < 1:
            raise ValueError("invalid compaction interval")
        protected = ledger["protected"]
        if (not isinstance(protected, list) or protected != sorted(set(protected))
                or any(type(i) is not int or not 0 <= i < 1 << circuit.qubits
                       for i in protected)):
            raise ValueError("invalid protected coordinate set")
        initial_exact = _fraction_state(initial)
        if tracking:
            if protected:
                raise ValueError("tracked mode cannot also declare fixed protected coordinates")
            if ledger.get("protection_mode") != MOVING_BRANCH_MODE:
                raise ValueError("unknown moving-branch protection mode")
            branch_origins = _branch_origins(ledger.get("protected_branches"), circuit.qubits)
            if list(branch_origins) != ledger.get("protected_branches"):
                raise ValueError("protected branch origins are not canonical")
            if any(origin not in initial for origin in branch_origins):
                raise ValueError("protected branch origin is absent from the initial state")
            if protected_branches is not None:
                expected_origins = _branch_origins(protected_branches, circuit.qubits)
                if expected_origins != branch_origins:
                    raise ValueError("protected branch origins do not match requested policy")
            positions = {origin: origin for origin in branch_origins}
            branch_values = {origin: initial_exact[origin] for origin in branch_origins}
        else:
            if protected_branches is not None:
                raise ValueError("certificate does not use moving-branch protection")
            if any(key in ledger for key in ("protection_mode", "protected_branches",
                                             "final_protected_positions")):
                raise ValueError("moving-branch metadata has the wrong semantics")
            branch_origins = ()
            positions = {}
            branch_values = {}
        if Fraction(ledger["budget"]) != budget:
            raise ValueError("ledger budget mismatch")
        events = ledger["events"]
        if not isinstance(events, list) or any(not isinstance(event, dict) for event in events):
            raise ValueError("invalid event list")
        if not isinstance(output_state, dict):
            raise ValueError("output state must be a dictionary")
        current = dict(initial_exact)
        reference = dict(current)
        remaining = TICKS
        event_index = 0
        total_charged = 0
        exact_deletion_mass = Fraction(0)
        for gate_index, gate in enumerate(gates, 1):
            if tracking and gate[0] == "z":
                bit = 1 << gate[1]
                for branch_index, origin in enumerate(branch_origins):
                    if branch_index % 256 == 0 and time.monotonic() >= deadline:
                        raise ValueError("moving-branch verification deadline exceeded")
                    if positions[origin] & bit:
                        real, imag = branch_values[origin]
                        branch_values[origin] = (-real, -imag)
            current = _gate_exact(current, gate)
            reference = _gate_exact(reference, gate)
            if tracking:
                positions = _move_branch_positions(positions, gate, deadline)
                protected_positions = set(positions.values())
                for origin, position in positions.items():
                    if time.monotonic() >= deadline:
                        raise ValueError("moving-branch verification deadline exceeded")
                    if position not in current or current[position] != branch_values[origin]:
                        raise ValueError(f"protected branch {origin} lost its exact Fraction amplitude")
            else:
                protected_positions = set()
            if event_index < len(events) and events[event_index].get("after_gate") == gate_index:
                event = events[event_index]
                if type(event["after_gate"]) is not int:
                    raise ValueError("invalid event position")
                if gate_index % interval and gate_index != len(gates):
                    raise ValueError("event violates compaction schedule")
                removed = event["removed"]
                if not isinstance(removed, list) or not removed:
                    raise ValueError("empty or malformed deletion witness")
                event_mass = Fraction(0)
                seen = set()
                for item in removed:
                    if not isinstance(item, list) or len(item) != 3:
                        raise ValueError("malformed deletion witness")
                    basis, real_hex, imag_hex = item
                    if type(basis) is not int or basis in seen or basis not in current:
                        raise ValueError("invalid or duplicate deletion index")
                    seen.add(basis)
                    if basis in protected or basis in protected_positions:
                        raise ValueError("protected coordinate was deleted")
                    witness = _decode_witness(real_hex, imag_hex)
                    if witness != current[basis]:
                        raise ValueError("deletion witness does not match exact replay")
                    event_mass += witness[0]**2 + witness[1]**2
                charge = event["ticks"]
                if type(charge) is not int or charge <= 0:
                    raise ValueError("invalid tick charge")
                exact_charge = _ceil_sqrt_fraction(
                    event_mass / (budget / ticks)**2, 1)
                if charge != exact_charge:
                    raise ValueError("event charge is not the exact minimum ceiling")
                if charge > remaining:
                    raise ValueError("cumulative budget exceeded")
                for basis in seen:
                    del current[basis]
                remaining -= charge
                total_charged += charge
                exact_deletion_mass += event_mass
                event_index += 1
        if event_index != len(events):
            raise ValueError("event order or position is invalid")
        if tracking:
            if time.monotonic() >= deadline:
                raise ValueError("moving-branch verification deadline exceeded")
            expected_positions = [[origin, positions[origin]] for origin in branch_origins]
            if ledger.get("final_protected_positions") != expected_positions:
                raise ValueError("final moving-branch position map mismatch")
        if not gates and events:
            raise ValueError("empty circuit cannot contain deletion events")
        charged_bound = budget * total_charged / ticks
        if Fraction(ledger["charged_l2"]) != charged_bound:
            raise ValueError("cumulative charge record mismatch")
        if Fraction(components["amplitude_deletion"]) != charged_bound:
            raise ValueError("deletion error component mismatch")
        if Fraction(components["total"]) != charged_bound or charged_bound > budget:
            raise ValueError("total certified error exceeds requested budget")
        if len(current) != len(output_state):
            raise ValueError("output support mismatch")
        for basis, pair in current.items():
            if basis not in output_state:
                raise ValueError("output basis mismatch")
            value = output_state[basis]
            if (_float_fraction(value.real), _float_fraction(value.imag)) != pair:
                raise ValueError("output amplitude differs from exact replay")
        # Exact unpruned-reference comparison. All values are binary rationals.
        diff_mass = Fraction(0)
        for basis in set(current) | set(reference):
            compacted = current.get(basis, (Fraction(0), Fraction(0)))
            original = reference.get(basis, (Fraction(0), Fraction(0)))
            diff_mass += (compacted[0]-original[0])**2 + (compacted[1]-original[1])**2
        if diff_mass > charged_bound**2:
            raise ValueError("exact final L2 error exceeds charged ledger")
        deletion_bound_squared = charged_bound**2
        return dict(status="PASS", exact_squared_error=f"{diff_mass.numerator}/{diff_mass.denominator}",
                    deletion_bound_squared=f"{deletion_bound_squared.numerator}/{deletion_bound_squared.denominator}",
                    exact_l2_interval=_root_interval(diff_mass),
                    certified_l2_bound=f"{charged_bound.numerator}/{charged_bound.denominator}",
                    exact_deleted_squared_mass=f"{exact_deletion_mass.numerator}/{exact_deletion_mass.denominator}",
                    coefficient_evaluation_error="0", complex_gate_arithmetic_error="0",
                    accumulated_gate_error="0", renormalization_error="0")
    except (ArithmeticError, KeyError, TypeError, ValueError, ZeroDivisionError, OverflowError, AttributeError) as exc:
        return dict(status="FAIL", reason=str(exc))
