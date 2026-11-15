# High-support connected-circuit verification

## Scope and distinction from earlier results

This experiment adds full, connected statevector cases at 17, 18, and 20 qubits. It is separate from the previously completed 120-circuit Qiskit/Cirq suite through six qubits and from the 40-qubit, 16,777,216-amplitude benchmark. That earlier large circuit factors into eight disconnected components; this document does not reinterpret it as one globally entangled 40-qubit system, and the old benchmark was not rerun.

The new seeded random-topology family has a connected two-qubit interaction graph, non-Clifford cross-cut phase gates, random intra-partition spanning trees, and local rotations. Every backend returns and compares the complete statevector. Qiskit `Statevector`, Cirq `Simulator`, SharkByte's existing sparse dictionary backend, and a separately written dense NumPy candidate are compared after global-phase alignment. The random circuit's balanced-cut Schmidt spectrum is independently compared with an analytic controlled-phase matrix. The local CX and one-qubit gates preserve that cut spectrum.

## Results

| Qubits | Exact nonzero amplitudes | Balanced cut | Schmidt rank at 1e-10 relative cutoff | Entropy / cut maximum | State comparison |
| ---: | ---: | ---: | ---: | ---: | --- |
| 17 | 131,072 | 8 | 256 / 256 | 7.126 / 8 bits (89.1%) | PASS |
| 18 | 262,144 | 9 | 512 / 512 | 8.046 / 9 bits (89.4%) | PASS |
| 20 | 1,048,576 | 10 | 1,024 / 1,024 | 9.005 / 10 bits (90.0%) | PASS |

For the 20-qubit random case, Qiskit and Cirq each match the independent analytic singular-value spectrum within 5.5e-16. All four complete statevectors match Qiskit within the recorded amplitude and probability tolerances; each input source, parsed gate sequence, plan, implementation file, and output vector has a SHA-256 digest in its receipt. The 17- and 18-qubit checks provide staged support increases; the 20-qubit check is the largest new connected, fully entangled case in this run.

A 20-qubit connected CNOT chain is included as a negative control. It has all 1,048,576 basis amplitudes but Schmidt rank 1 and purity 1 across the balanced cut. Thus graph connectivity and dense support alone do not establish entanglement.

Forward/inverse cancellation cases at 17 and 18 qubits return the all-zero basis state with maximum off-target amplitude below 1.4e-16 on the tested backends. **Observed limitation:** floating-point residuals remain exactly nonzero in the stored dictionaries, so reported final support stays at 131,072 and 262,144 instead of collapsing to one. The exact simulator does not prune small amplitudes. This behavior is reported without thresholding; introducing pruning would change exact semantics and needs a separately specified approximation/error budget.

A 17-qubit adversarial circuit applies inverse-paired rotations and controlled phases near ±4π and at the 4π endpoint. It remains inside the parser's documented angle limit and agrees across the compared backends; the final state remains separable.

## Running the experiment

Use Python 3.12 and the pinned references:

```powershell
python -m pip install -r requirements-high-support.txt
python -B -m unittest validation.high_support.test_high_support -v
python -B tools/high_support/generate.py --source-dir examples/high_support --plan-dir validation/high_support/plans
python -B tools/high_support/run_suite.py --case random_connected --width 20 --output-dir results/random20 --repeat 3
```

The suite runner invokes Qiskit, Cirq, dense NumPy, and sparse SharkByte sequentially, then writes the full-vector comparison. For the 17- and 18-qubit cases, replace `20` with `17` or `18`. The other cases are `connected_separable` at 20 qubits, `numerical_adversary` at 17 qubits, and `roundtrip` at 17 or 18 qubits. Preserve the `.npy` files for a later independent recheck; the comparison receipt records their hashes.

CI runs the randomized 20-qubit case, the connected separable negative control, the near-4π adversary, and the 17-qubit roundtrip. It does not rerun the old 120-circuit or 16.7-million-amplitude suites.

## Performance and limits

The existing sparse implementation is measured without changing its exact behavior. A separate dense NumPy implementation is used as an exploratory performance candidate; it is not enabled in the product. Each receipt records repeated elapsed times and medians, peak process memory, host CPU, Python/NumPy/reference versions, and hashes for the source and implementations. Sparse measurements include conversion to a complete dense vector for archival/comparison, separately timed from sparse evolution.

These are classical CPU simulations, not quantum hardware runs. Circuits above 20 qubits, circuits exceeding the checked-in source support, and execution on a QPU are NOT TESTED here. A connected graph is not itself an entanglement proof; entanglement claims are based on the independently computed statevector Schmidt spectra.