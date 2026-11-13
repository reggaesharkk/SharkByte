# Experimental Frontier30 source benchmark

Run from the checkout root with CPython 3.10 or later.

    python -B benchmarks/sb_quantum_benchmark/sb_end_to_end_bench.py

The benchmark uses a separate copy of the quantum parser adapted for sparse circuits. It checks complex amplitudes against analytical expectations and verifies refusal above a 4,096-state cap. Peak memory measures Python allocations with tracemalloc. The included report records one instrumented laptop run. The record hash covers sorted-key JSON of the report before the hash field is added.
