# Working grammar (scoped subset)

This is a descriptive grammar for the checked-in alpha examples and accepted test subset. The implementation parser is authoritative; this document is not a complete or normative language specification.

```ebnf
program       = { statement } ;
statement     = declaration | assignment | print_stmt | if_stmt | while_stmt
              | return_stmt | function_decl ;
declaration   = "let" identifier "=" expression ";" ;
assignment   = identifier "=" expression ";"
              | identifier "[" expression "]" "=" expression ";" ;
print_stmt    = "print" expression ";" ;
if_stmt       = "if" "(" condition ")" block [ "else" block ] ;
while_stmt    = "while" "(" condition ")" block ;
function_decl = "fun" identifier "(" [ identifiers ] ")" block ;
return_stmt   = "return" expression ";" ;
block         = "{" { statement } "}" ;
expression    = integer | identifier | array_expr | call | unary_expr
              | binary_expr | "(" expression ")" ;
array_expr    = "array" "(" expression ")" ;
call          = identifier "(" [ expressions ] ")" ;
```

## Quantum and Frontier30

Studio runs quantum circuits separately from classical programs. Use a named
`quantum` block, as in the [Bell example](examples/bell.sb) or the
[phase-flip recovery circuit](examples/phase_flip_recovery.sb).

```ebnf
quantum_block = "quantum" identifier "{" { quantum_statement } "}" ;
quantum_statement = "qubits" integer ";"
                  | "shots" integer ";"
                  | "seed" integer ";"
                  | ( "h" | "x" | "z" ) qubit ";"
                  | "cx" qubit qubit ";"
                  | "cp" signed_decimal qubit qubit ";"
                  | rotation_gate
                  | "measure_all" ";" ;
rotation_gate     = ( "rx" | "ry" | "rz" ) signed_decimal qubit ";" ;
signed_decimal    = [ "+" | "-" ] ( digits [ "." [ digits ] ] | "." digits ) ;
digits            = digit { digit } ;
digit             = "0" | "1" | "2" | "3" | "4" | "5" | "6" | "7" | "8" | "9" ;
```

Declare `qubits` once before the gates and end the gate sequence with
`measure_all;`. Qubit indices start at zero. For `cx` and `cp`, give the
control before the target and use distinct indices. Controlled phase takes a
decimal angle in radians. Rotations use angles in radians within ±4π in
Quantum and Frontier30. For example, `ry -.5 0;` rotates qubit 0 by −0.5
radians. Frontier30 checks the potential expansion of `rx` and `ry` before
applying them. `rz` preserves sparse support.
Multiple statements can share a line, and `//`
starts a line comment.

Studio Quantum accepts 1–6 qubits and reports probabilities and sampled
counts. Frontier30 uses the same gate syntax for fixed-angle circuits with
registers up to 40 qubits. The selected sparse support cap limits the number
of active basis states. Frontier30 reports probabilities. See the
[40-qubit example](examples/frontier_sparse_40_131072.sb).

## Bounded Hybrid

Start with `hybrid NAME { ... }` and put the blocks in this order:
`prepare`, `quantum`, `feedback`, then `update` for the adaptive form.
The [adaptive example](examples/adaptive.sb) shows the full syntax.

- `prepare` sets circuit and loop parameters such as `qubits`, `shots`,
  `seed`, `theta`, `step`, and `iterations`.
- `quantum` contains gates and `measure_all;`. The qubit count comes from
  `prepare`. Rotation and controlled-phase angles accept a signed decimal
  or the name `theta`, within ±π. For example, `ry theta 0;` uses the value
  bound for that iteration. The hybrid receipt records the generated circuit
  with its numeric angle.
- `feedback` reads measurement values such as `count_00` and can print
  results or branch on comparisons.
- `update` can change `theta` for the next iteration, for example with
  `theta = theta - step;`.

Bounded Hybrid supports 2–6 qubits and 1–8 iterations. See [SPEC.md](SPEC.md)
for the CLI limits. The Studio phase-flip noise sweep is controlled by the UI.
