# Experimental Frontier30 source benchmark

Run from the checkout root with CPython 3.10 or later.

    python -B benchmarks/sb_quantum_benchmark/sb_end_to_end_bench.py --output benchmarks/sb_quantum_benchmark/results.json

The command prints the full JSON receipt and refreshes the checked-in `results.json`. The receipt includes SHA-256 hashes for every source module used by the benchmark, each circuit source, and the complete record. Timings and peak Python memory are measurements from the machine that ran it, so they can vary between runs. Commit an updated receipt only when it was generated from the source being committed.

Run a supported `.sb` quantum block from the checkout root:

    python -B benchmarks/sb_quantum_benchmark/frontier30.py benchmarks/sb_quantum_benchmark/branch13.sb --support-cap 8192 --timeout 5

The command defaults to 4,096 populated basis states and a five-second evolution deadline. Use `--support-cap 8192` or `--support-cap 16384` for larger sparse circuits. Its JSON report includes probabilities, final and peak support, the first gate that reached peak support, and elapsed evolution time. Gate indices start at zero. A null peak gate means the peak was already present in the initial state. The command returns 0 on success, 1 on resource refusal, and 2 for invalid input. Refusals report the affected gate when available and the projected support when a gate would exceed the cap.

The command computes probabilities directly from the sparse statevector. Use the benchmark for independent amplitude comparisons. The bundled benchmark checks its circuits against analytical expectations and verifies the 4,096-state boundary. Peak support comes from one evolution pass. Peak memory measures Python allocations with tracemalloc. The `--output` receipt hash covers sorted-key JSON before the hash field is added.

The larger `--support-cap` example above is a separate CPU experiment. Its result is not part of the checked-in 4,096-state benchmark receipt and does not imply quantum hardware or NPU execution.
