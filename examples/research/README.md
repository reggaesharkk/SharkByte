# Research gap calculations in SharkByte

These small `.sb` programs use SharkByte's own integer VM to recalculate selected arithmetic from the wider research portfolio. Start with the [guide](../../docs/RESEARCH_GAP_CALCULATIONS.md), which states each input source, unit, command, and evidence limit.

From the SharkByte repository root, run each with:

```sh
python -B -m sharkbyte_alpha run examples/research/navier_m15_gap.sb --backend vm
python -B -m sharkbyte_alpha run examples/research/riemann_wp84_count.sb --backend vm
python -B -m sharkbyte_alpha run examples/research/protocol_wp19_assumed_rates.sb --backend vm
python -B -m sharkbyte_alpha run examples/research/strength_b3_threshold.sb --backend vm
```

The results are bounded calculations over stated inputs. They do not replace Arb interval certificates, Lean proofs, source-data reproduction, independent review, or empirical validation.
