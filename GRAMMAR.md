# Working grammar (scoped subset)

This is a descriptive grammar for the checked-in alpha examples and accepted test subset. The implementation parser is authoritative; this document is not a complete or normative language specification.

```ebnf
program       = { statement } ;
statement     = declaration | assignment | print_stmt | if_stmt | while_stmt
              | return_stmt | function_decl | quantum_block | feedback_block
              | update_block ;
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

Quantum and hybrid statements are a restricted DSL described by the checked-in examples and parser tests, not general-purpose embedded Python. The supported implementation imposes source, instruction, qubit, gate, shot, and iteration limits documented in `SPEC.md`. Native backends are disabled. Unsupported syntax fails rather than being silently translated.
