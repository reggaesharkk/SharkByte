"""Generate deterministic high-support sources, plans, and a connected control."""
import argparse
import json
from pathlib import Path
import sys
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from validation.high_support.common import WIDTHS, generate_plan, render_source, sha256, is_two_qubit_graph_connected


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-dir", type=Path, required=True)
    parser.add_argument("--plan-dir", type=Path, required=True)
    args = parser.parse_args()
    args.source_dir.mkdir(parents=True, exist_ok=True)
    args.plan_dir.mkdir(parents=True, exist_ok=True)
    plans = []
    for case, widths in (("entangled", WIDTHS), ("random_connected", WIDTHS), ("connected_separable", (20,)), ("numerical_adversary", (17,)), ("roundtrip", (17, 18))):
        for width in widths:
            plan = generate_plan(width, case)
            if not is_two_qubit_graph_connected(plan):
                raise SystemExit(f"disconnected generated gate graph: {case} {width}q")
            raw = render_source(plan)
            source_path = args.source_dir / f"{case}_{width}q.sbq"
            plan_path = args.plan_dir / f"{case}_{width}q.plan.json"
            source_path.write_bytes(raw)
            plan["source_sha256"] = sha256(raw)
            plan_path.write_text(json.dumps(plan, indent=2, sort_keys=True, allow_nan=False) + "\n", encoding="utf-8")
            plans.append({"case": case, "qubits": width, "gates": len(plan["gates"]),
                          "two_qubit_graph_connected": True, "topology_kind": plan.get("topology_kind"), "source": source_path.name,
                          "source_sha256": plan["source_sha256"],
                          "gate_sequence_sha256": plan["gate_sequence_sha256"]})
    print(json.dumps(plans, indent=2))

if __name__ == "__main__":
    main()