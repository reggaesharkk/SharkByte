# Research gap calculations in SharkByte

These small `.sb` programs use SharkByte's own integer VM to recalculate selected arithmetic from the wider research portfolio. Start with the [guide](../../docs/RESEARCH_GAP_CALCULATIONS.md), which states each input source, unit, command, and evidence limit.

From the SharkByte repository root, run each with:

```sh
python -B -m sharkbyte_alpha run examples/research/navier_m15_gap.sb --backend vm
python -B -m sharkbyte_alpha run examples/research/bounded_existence_thresholds.sb --backend vm
python -B -m sharkbyte_alpha run examples/research/bounded_existence_floors.sb --backend vm
python -B -m sharkbyte_alpha run examples/research/riemann_wp84_count.sb --backend vm
python -B -m sharkbyte_alpha run examples/research/protocol_wp19_assumed_rates.sb --backend vm
python -B -m sharkbyte_alpha run examples/research/strength_b3_threshold.sb --backend vm
python -B -m sharkbyte_alpha run examples/research/strength_h2_reset_gate.sb --backend vm
python -B -m sharkbyte_alpha run examples/research/strength_h4_split_audit.sb --backend vm
python -B -m sharkbyte_alpha run examples/research/gradient_descent_linear_fit.sb --backend vm
python -B -m sharkbyte_alpha run examples/research/recurrent_bptt_memory.sb --backend vm
```

The B3 threshold program recalculates the recorded guard arithmetic. The H2 program demonstrates a reset branch using synthetic gradient vectors; it is not a network interceptor or efficacy test. The H4 program checks a reproducible 80/20 partition over synthetic IDs using SharkByte's own shuffle, not NumPy's exact permutation; it does not calculate information gain or validate a data set. The scalar fit trains one toy fixed-point weight inside SharkVM; it is not the B3 recurrent model or a language-model fine-tune.

The recurrent example performs a three-step synthetic recurrence and 30 analytic BPTT updates to one scalar weight inside SharkVM. It demonstrates gradient calculation and parameter updates in SharkByte; it is not the STRENGTH B3 model, its private experiment, or an LLM fine-tune.

The bounded-existence example uses exact integer cross-products to check the paper's `P0 > 10/99` domain and compare three rational Hopf-threshold samples with the stated fractions. It does not integrate the ODE or prove bounded existence.

The bounded-existence floor example evaluates the paper's displayed rational lower-bound formulas at one stated parameter tuple. It does not integrate the system or replace the paper's Lean and continuous-time comparison arguments.

All results are bounded calculations over stated inputs. They do not replace Arb interval certificates, Lean proofs, source-data reproduction, independent review, or empirical validation.
