# Working grammar (scoped alpha subset)

This EBNF describes the checked-in classical, quantum, and bounded-hybrid examples and tested subset. The implementation parser and regression tests are authoritative; this is not a complete or normative language specification. The alpha CLI selects a mode, so a source file is interpreted as one of the program forms below.

```ebnf
classical_program = { statement } ;
statement         = declaration | assignment | print_stmt | if_stmt
                  | while_stmt | return_stmt | function_decl ;
declaration       = "let" identifier "=" expression ";" ;
assignment        = identifier "=" expression ";"
                  | identifier "[" expression "]" "=" expression ";" ;
print_stmt        = "print" expression ";" ;
if_stmt           = "if" "(" condition ")" block [ "else" block ] ;
while_stmt        = "while" "(" condition ")" block ;
function_decl     = "fun" identifier "(" [ identifier_list ] ")" block ;
return_stmt       = "return" expression ";" ;
block             = "{" { statement } "}" ;
expression        = integer | identifier | array_expr | call | unary_expr
                  | binary_expr | "(" expression ")" ;
array_expr        = "array" "(" expression ")" ;
call              = identifier "(" [ expression_list ] ")" ;

quantum_program   = "qubits" integer ";" { quantum_statement }
                    "measure_all" ";" ;
quantum_statement = one_qubit_gate | controlled_not | controlled_phase
                  | "shots" integer ";" | "seed" integer ";" ;
one_qubit_gate    = ( "h" | "x" | "z" ) integer ";" ;
controlled_not    = "cx" integer integer ";" ;
controlled_phase  = "cp" decimal_literal integer integer ";" ;

hybrid_program    = "hybrid" identifier "{" prepare_block quantum_block
                    feedback_block update_block "}" ;
prepare_block     = "prepare" "{" prepare_field prepare_field
                    prepare_field prepare_field prepare_field
                    prepare_field "}" ;
prepare_field     = "qubits" "=" integer ";"
                  | "shots" "=" integer ";"
                  | "seed" "=" integer ";"
                  | "theta" "=" decimal_literal ";"
                  | "step" "=" decimal_literal ";"
                  | "iterations" "=" integer_expression ";" ;
quantum_block     = "quantum" "{" { hybrid_quantum_statement } "}" ;
hybrid_quantum_statement = one_qubit_gate | controlled_not
                         | "cp" ( "theta" | decimal_literal )
                           integer integer ";"
                         | "measure_all" ";" ;
feedback_block   = "feedback" "{" { feedback_statement } "}" ;
feedback_statement = feedback_print | feedback_if ;
feedback_print   = "print" feedback_expression ";" ;
feedback_if      = "if" "(" feedback_condition ")" feedback_body
                   [ "else" feedback_body ] ;
feedback_body    = "{" { feedback_statement } "}" ;
update_block     = "update" "{" update_if_else "}" ;
update_if_else   = "if" "(" update_condition ")" "{"
                   "theta" "=" "theta" ( "+" | "-" ) "step" ";" "}"
                   "else" "{" "theta" "=" "theta" ";" "}" ;

identifier       = letter { letter | digit | "_" } ;
identifier_list  = identifier { "," identifier } ;
expression_list  = expression { "," expression } ;
integer          = [ "+" | "-" ] digit { digit } ;
decimal_literal  = [ "+" | "-" ] ( digit { digit } [ "." { digit } ]
                  | "." digit { digit } ) ;
letter           = "A" … "Z" | "a" … "z" | "_" ;
digit            = "0" … "9" ;
```

The productions named `condition`, `unary_expr`, `binary_expr`, `integer_expression`, `feedback_expression`, `feedback_condition`, and `update_condition` denote restricted expression forms accepted by the corresponding implementation parser; this shorthand does not expand their operator tables. In hybrid `prepare`, the six fields shown are each required exactly once, in any order; other or duplicate fields are rejected. Hybrid blocks must appear once and in the shown order, with no trailing source. `theta` is bounded to `[-pi, pi]`, `step` to `(0, pi]`, and iterations to 1–8. Quantum circuits are limited to 2–6 qubits and 256 gates; other source, instruction, shot, and resource limits are documented in `SPEC.md`.

Hybrid feedback accepts only bounded `print` and `if`/`else` statements with integer arithmetic over measurement-count variables; nesting and statement counts are limited. The update block supports one guarded `theta = theta +/- step` update with a no-op `else`. Hybrid execution is a bounded outer Python orchestrator that runs one supported quantum circuit per iteration. This does not mean the nested quantum executor supports arbitrary iterative quantum-classical loops. Native backends are disabled. The quantum mode is classical statevector simulation, not quantum hardware. Unsupported syntax is rejected rather than silently translated.
