# What can SharkByte calculate today?

SharkByte can run classical integer programs and bounded quantum circuits written in its own `.sb` language. The quantum results below come from classical CPU simulators; they are not runs on quantum hardware. GenieX/NPU chat is a separate feature and does not accelerate the simulator.

## At a glance

| Workload | Current documented range | Example | What sets the limit |
| --- | --- | --- | --- |
| Classical SharkVM | Source up to 65,536 UTF-8 bytes; up to 50,000,000 VM instructions | `examples/drawdown_risk_demo.sb` | VM instruction and source-size bounds |
| Quantum statevector | 1–6 qubits, up to 256 gates and 100,000 shots | `examples/bell.sb` | Dense statevector simulation on the CPU |
| Hybrid VM + quantum | 2–6 qubits, up to 100,000 VM instructions and 1–8 iterations | `examples/adaptive.sb` | Bounded hybrid implementation |
| Frontier30 sparse simulation | Current benchmark uses a 30-qubit register; parser accepts up to 40 qubits. Default cap is 4,096 populated basis states. | `benchmarks/sb_quantum_benchmark/branch12.sb` | Sparse-state support cap, not total register width |

These are implementation bounds, not a claim that every program at the limit is fast or useful. A run can also be refused for invalid syntax, unsupported gates, or a resource cap.

## Try a real classical calculation

From the repository root, run:

```sh
python -B -m sharkbyte_alpha run examples/drawdown_risk_demo.sb --backend vm
```

On Ubuntu, use `python3` instead of `python`. The bundled program performs integer fixed-point arithmetic, including a Padé approximation to `tanh(0.5)`. It prints:

```text
500000
462117
2310585
```

Those values are the input ratio in parts per million, the approximated multiplier in parts per million, and an example quantity scaled to millionths. SharkVM executes 85 instructions for this example. It is a language and arithmetic demonstration; it does not generate a trading signal or place an order.

For a minimal program that prints 42, run `python -B -m sharkbyte_alpha run examples/example.sb --backend vm`.

## Try the standard quantum simulator

Run the Bell circuit:

```sh
python -B -m sharkbyte_alpha run examples/bell.sb --mode quantum --backend vm
```

The example prepares a two-qubit Bell state. Its ideal measurement probabilities are 50% for `00`, 50% for `11`, and zero for `01` and `10`. The documented statevector mode supports at most six qubits (64 amplitudes), 256 gates, and 100,000 shots. It runs on the CPU.

## Try the 30-qubit sparse examples

Start the interactive terminal with `python -B sharkbyte_terminal.py` (use `python3` on Ubuntu), then enter `/qft` at its `You:` prompt. The bundled circuit uses a six-qubit QFT inside a 30-qubit register. Its current input produces 32 populated states at probability `1/32` each; the other 24 spectator qubits are not targeted by any gate and remain zero. Although the sparse parser accepts registers up to 40 qubits, the checked-in benchmark evidence here is for 30-qubit examples, not a 40-qubit performance claim.

Frontier30 stores only populated states, so its 30-qubit label does **not** mean it allocates a dense `2^30`-amplitude vector (over one billion basis states). The standard benchmark cap is 4,096 populated states:

- `branch12.sb` reaches 4,096 states and fits the cap.
- `branch13.sb` would reach 8,192 and is refused by the standard 4,096-state cap.
- The standalone script accepts larger experimental caps, but those runs are separate from the checked-in 4,096-state benchmark and consume more memory and time.

To run the boundary examples from the repository root:

```sh
python -B benchmarks/sb_quantum_benchmark/frontier30.py benchmarks/sb_quantum_benchmark/branch12.sb
python -B benchmarks/sb_quantum_benchmark/frontier30.py benchmarks/sb_quantum_benchmark/branch13.sb
```

The second command is expected to refuse the circuit at the default cap. Ubuntu uses `python3` in both commands.

## What these numbers do not mean

- A 30-qubit sparse register is not a general dense 30-qubit simulator. The reachable nonzero-state count is capped.
- Quantum and Frontier30 examples run on the CPU, not a quantum processor or NPU.
- The terminal's local model can explain a calculation, but simulator output is the source for calculated probabilities.
- Native AArch64 execution is disabled in this distribution. SharkVM is not an operating-system security sandbox.
- Fixed-point approximations are not arbitrary-precision real arithmetic. Check the source, units, and approximation before reusing a value.

See [`SPEC.md`](../SPEC.md), [`GRAMMAR.md`](../GRAMMAR.md), and the [Frontier30 benchmark notes](../benchmarks/sb_quantum_benchmark/README.md) for exact bounds and evidence scope.
