# Recalculating open research gaps with SharkByte

These examples use the SharkByte `.sb` language and its bounded integer VM to make four research calculations repeatable. The programs are diagnostics over published or locally archived inputs. A result from SharkByte does not upgrade an input from assumed to certified, reproduce an omitted source dataset, or close an open theorem.

## Run them

From the root of the SharkByte repository:

```sh
python -B -m sharkbyte_alpha run examples/research/navier_m15_gap.sb --backend vm
python -B -m sharkbyte_alpha run examples/research/riemann_wp84_count.sb --backend vm
python -B -m sharkbyte_alpha run examples/research/protocol_wp19_assumed_rates.sb --backend vm
python -B -m sharkbyte_alpha run examples/research/strength_b3_threshold.sb --backend vm
```

These commands run `.sb` source in SharkVM. They do not call Python implementations from the other projects. The VM uses signed 64-bit integer arithmetic, so the examples use scaled integers and keep intermediates within that range. The protocol recurrence is a fixed-point Taylor approximation, not interval arithmetic.

## What each calculation says

### Navier–Stokes M15 margin

`navier_m15_gap.sb` subtracts the recorded signed C500 lower bound from the recorded M15 remainder upper bound. Its first three outputs are, in order, remainder, lower bound, and signed margin, in thousandths of the original units. The fourth output is an approximate remainder/lower ratio in thousandths of a factor.

The current recorded values are approximately `1.6406308768e14` for the remainder and `5.7585744356e9` for the signed lower bound. The negative margin reproduces why this route does not close. Rounding in the source constants and the division used for the ratio are explicit; this is not a fresh Arb enclosure.

SharkByte output (scaled integers): `164063087678950089`, `5758574435606`, `-164057329104514483`, `28490226`. The last value means about `28,490.226×` because it is a thousandths-of-a-factor output.

The public Navier repository describes its certificates as finite and conditional and keeps continuum regularity open: [project README](https://github.com/reggaesharkk/navier-stokes-bridge-audit), [WP19 bridge evidence inventory](https://github.com/reggaesharkk/navier-stokes-bridge-audit/tree/main/results/wp19_bridge), and [current WP19 status](https://github.com/reggaesharkk/navier-stokes-bridge-audit/blob/main/notes/WP19_CURRENT_STATUS_2026_09_30.md).

### Riemann/WP84 finite-certificate scale and open threshold

Assuming “Raman” meant the Riemann/WP84 project, `riemann_wp84_count.sb` enumerates all strictly increasing 4-tuples from 45 reported hyperplanes in SharkByte. It should count `148,995` candidates. It also reports the published finite certificate's 151 relevant vertices as a fraction of that count, derives the `11061/13891` model frontier in thousandths of a percent, and prints the truncated parts-per-billion form of the separate required source-saving threshold.

The source-weighted signed third/fifth/sixth saving is still not supplied by that finite count. The documented threshold is strictly greater than `0.002057354918974498…`; transfer estimates and strict slack remain unpaid. Thus the reported model frontier is not an unconditional zero-proportion theorem, and this calculation says nothing about proving the Riemann Hypothesis.

Sources: [Riemann/WP84 release and contribution register](https://github.com/reggaesharkk/Reggae-shark-universe-/blob/main/papers/riemann/RELEASE_AND_CONTRIBUTION_REGISTER_2026_10_09.md), [public WP84 repository](https://github.com/reggaesharkk/riemann-bandwidth1-verification).

SharkByte output: `148995` candidates; `151` reported vertices; `1013` parts per million; `79627` thousandths of a percentage point (79.627%); `627` thousandths of a percentage point above 79%; and `2057354` truncated parts per billion for the required saving threshold.

### Shark Protocol's 120-step assumed-rate study

`protocol_wp19_assumed_rates.sb` implements two recurrences, `E[n+1] = exp(rate * dt) * E[n] + defect`, for 120 equal steps over `T=1.20`. It uses the protocol file's assumed rates `24.50` and `-3.50`, defect `2.35e-4`, a `1e6` fixed-point scale, and 20 Taylor terms. Outputs are the two approximate per-step factors, the two final errors in micro-units, the signed C500 lower bound in micro-units, and its margin over the whole-path model error.

That output is only a SharkByte-language replay of the illustrative parameter study. With the documented assumptions it prints factors `1.277619` and `0.965605`, corresponding to approximate recurrence errors `4,955,569,994.441750` and `0.006716`. The first recurrence alone appears below the signed C500 lower bound by about `803,030,005.558250`, but the dataset separately preserves a whole-path remainder of `163,640,000,000,000`, which exceeds the `5,758,600,000` signed lower bound by `163,634,241,400,000`. That preserved bound is still a negative margin, so the apparent recurrence margin does not close the gate.

The original protocol labels these rates assumed and says a per-segment Arb enclosure is needed before using them as Navier–Stokes bounds. The fixed-point recurrence here is not outward rounded and must not be read as a rigorous interval result. Sources: [protocol study inputs](https://github.com/reggaesharkk/The-Reggae-Shark-Protocol/blob/main/data/wp19_segments.json), [study implementation and evidence boundary](https://github.com/reggaesharkk/The-Reggae-Shark-Protocol/blob/main/shark_protocol/kernel.py).

### STRENGTH B3 guard thresholds

`strength_b3_threshold.sb` recalculates the B3 guard's algebraic velocity ceiling from `velocity * 0.184920 <= 49123.01`, checks the maximum thousandth-unit velocity and the next increment, then computes the source example's contracted value and strain margin. Values ending in hundredths or thousandths are printed as scaled integers, as stated in the source comments.

This only checks arithmetic implied by the Python constants. It does not establish that the constants are calibrated, the model is effective, the Lean statements cover the runtime implementation, or the guard provides a security boundary. Source: [STRENGTH-INTENT-NS-LEAN source](https://github.com/reggaesharkk/strength-intent-ns-lean).

SharkByte output: maximum allowed velocity is `265644657` thousandths (`265,644.657`) at the configured constants; the next thousandth breaches the exact scaled ceiling. For the source example, the contracted value prints as `231159` cents (`2,311.59` when truncated to cents), the Lipschitz margin is `4681142` cents, and strain margin is `3803302` cents.

## Why more work remains

The largest missing items are not “more arithmetic” alone: Navier needs a valid signed remainder enclosure with the right sign and the missing modewise/transfer evidence; Riemann needs the actual arithmetic source-weighted saving and prime-to-Weil/zero-side transfers; Protocol needs independently certified rates rather than assumptions; and STRENGTH needs validation and evidence that its mathematical assumptions correspond to the deployed behavior. SharkByte makes these gates easier to measure and reproduce, but does not make them disappear.
