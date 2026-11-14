# Experimental Frontier30 source benchmark

Run from the checkout root with CPython 3.10 or later.

    python -B benchmarks/sb_quantum_benchmark/sb_end_to_end_bench.py

Run a supported `.sb` quantum block from the checkout root:

    python -B benchmarks/sb_quantum_benchmark/frontier30.py benchmarks/sb_quantum_benchmark/branch13.sb --support-cap 8192 --timeout 5

The command defaults to 4,096 populated basis states and a five-second evolution deadline. Use `--support-cap 8192` or `--support-cap 16384` for larger sparse circuits. Its JSON report includes probabilities, final and peak support, the first gate that reached peak support, and elapsed evolution time. Gate indices start at zero. A null peak gate means the peak was already present in the initial state. The command returns 0 on success, 1 on resource refusal, and 2 for invalid input. Refusals report the affected gate when available and the projected support when a gate would exceed the cap.

The command computes probabilities directly from the sparse statevector. Use the benchmark for independent amplitude comparisons. The benchmark checks its bundled circuits against analytical expectations and verifies the 4,096-state boundary. Peak support comes from one evolution pass. Peak memory measures Python allocations with tracemalloc. The included report records an earlier instrumented laptop run. Both report hashes cover sorted-key JSON before the hash field is added.
