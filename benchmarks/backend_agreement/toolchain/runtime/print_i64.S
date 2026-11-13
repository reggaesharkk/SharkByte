/* AAPCS64 numeric output routine; argument is signed i64 in x0. */
.text
.global sb_print_i64
.type sb_print_i64, %function
sb_print_i64:
    stp x29, x30, [sp, #-64]!
    mov x29, sp
    /* Leave one byte after the digits/sign for newline within this frame. */
    add x1, sp, #62
    mov x2, #0
    mov x10, #0
    cmp x0, #0
    b.ge .Lsb_print_magnitude
    mov x10, #1
    neg x0, x0
.Lsb_print_magnitude:
    mov x6, #10
.Lsb_print_digits:
    udiv x4, x0, x6
    msub x5, x4, x6, x0
    add w5, w5, #48
    strb w5, [x1]
    sub x1, x1, #1
    add x2, x2, #1
    mov x0, x4
    cmp x0, #0
    b.ne .Lsb_print_digits
    cbz x10, .Lsb_print_newline
    mov w5, #45
    strb w5, [x1]
    sub x1, x1, #1
    add x2, x2, #1
.Lsb_print_newline:
    add x1, x1, #1
    add x4, x1, x2
    mov w5, #10
    strb w5, [x4]
    add x2, x2, #1
    mov x0, #1
    bl sb_write_all
    ldp x29, x30, [sp], #64
    ret
.size sb_print_i64, .-sb_print_i64
.section .note.GNU-stack,"",%progbits
