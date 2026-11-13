/* Minimal freestanding Linux/AArch64 support for direct v0.6 executables. */
#include <stdint.h>
#include <stddef.h>

#define SB_DIRECT_TICK_LIMIT 50000000ULL
#define SB_CALL_DEPTH_LIMIT 128U
#define SB_MAX_ARRAY_LENGTH 65536U
#define SB_MAX_ARRAYS 4096U
#define SB_MAX_HEAP_ELEMENTS 65536U
#define SB_TAG_INTEGER 0U
#define SB_TAG_ARRAY 1U

static uint64_t sb_ticks;
static uint32_t sb_call_depth;
static uint32_t sb_array_count;
static uint32_t sb_heap_elements;
static uint64_t sb_heap[SB_MAX_HEAP_ELEMENTS];
static uint32_t sb_array_start[SB_MAX_ARRAYS + 1U];
static uint32_t sb_array_length[SB_MAX_ARRAYS + 1U];
static uint8_t sb_array_valid[SB_MAX_ARRAYS + 1U];

typedef struct { uint64_t payload; uint64_t tag; } sb_value;

static long sb_sys_write(long fd, const void *buffer, long length) {
    register long x0 __asm__("x0") = fd;
    register const void *x1 __asm__("x1") = buffer;
    register long x2 __asm__("x2") = length;
    register long x8 __asm__("x8") = 64;
    __asm__ volatile("svc #0" : "+r"(x0) : "r"(x1), "r"(x2), "r"(x8) : "memory");
    return x0;
}

__attribute__((noreturn)) static void sb_sys_exit(int status) {
    register long x0 __asm__("x0") = status;
    register long x8 __asm__("x8") = 93;
    __asm__ volatile("svc #0" : : "r"(x0), "r"(x8) : "memory");
    __builtin_unreachable();
}

void sb_write_all(long fd, const char *data, long length) {
    while (length > 0) {
        long written = sb_sys_write(fd, data, length);
        if (written <= 0) return;
        data += written;
        length -= written;
    }
}

__attribute__((noreturn)) static void sb_fail(const char *message, long length) {
    sb_write_all(2, message, length);
    sb_write_all(2, "\n", 1);
    sb_sys_exit(70);
}

void sb_error_divzero(void) { sb_fail("Division by zero", 16); }
void sb_error_divoverflow(void) { sb_fail("Integer division overflow", 25); }
void sb_error_missing_return(void) { sb_fail("Function ended without return", 29); }
void sb_error_stack_depth(void) { sb_fail("Call depth limit exceeded", 25); }
void sb_error_stack_balance(void) { sb_fail("Native evaluation stack imbalance", 33); }
void sb_error_integer(void) { sb_fail("Expected integer value", 22); }

void sb_tick(void) {
    if (sb_ticks >= SB_DIRECT_TICK_LIMIT)
        sb_fail("Execution step limit exceeded", 29);
    ++sb_ticks;
}

void sb_enter(void) {
    if (sb_call_depth >= SB_CALL_DEPTH_LIMIT)
        sb_error_stack_depth();
    ++sb_call_depth;
}

void sb_leave(void) {
    if (sb_call_depth == 0)
        sb_error_stack_balance();
    --sb_call_depth;
}

void sb_putc(int64_t code) {
    if (code < 0 || code > 127)
        sb_fail("Character code outside ASCII range 0..127", 41);
    char byte = (char)code;
    sb_write_all(1, &byte, 1);
}

sb_value sb_new_array(int64_t length) {
    if (length < 0) sb_fail("Negative array length", 21);
    if ((uint64_t)length > SB_MAX_ARRAY_LENGTH || sb_array_count >= SB_MAX_ARRAYS ||
        sb_heap_elements + (uint64_t)length > SB_MAX_HEAP_ELEMENTS)
        sb_fail("Array heap limit exceeded", 25);
    uint32_t handle = ++sb_array_count;
    uint32_t start = sb_heap_elements;
    sb_array_start[handle] = start;
    sb_array_length[handle] = (uint32_t)length;
    sb_array_valid[handle] = 1;
    for (uint32_t i = 0; i < (uint32_t)length; ++i) sb_heap[start + i] = 0;
    sb_heap_elements += (uint32_t)length;
    sb_value result = {handle, SB_TAG_ARRAY};
    return result;
}

static uint32_t sb_validate_array(uint64_t handle, uint64_t tag) {
    if (tag != SB_TAG_ARRAY || handle == 0 || handle > SB_MAX_ARRAYS || !sb_array_valid[handle])
        sb_fail("Expected array reference", 24);
    return (uint32_t)handle;
}

sb_value sb_load_index(uint64_t handle, uint64_t tag, int64_t index, uint64_t index_tag) {
    if (index_tag != SB_TAG_INTEGER) sb_error_integer();
    uint32_t id = sb_validate_array(handle, tag);
    if (index < 0 || (uint64_t)index >= sb_array_length[id])
        sb_fail("Array index out of bounds", 25);
    sb_value result = {sb_heap[sb_array_start[id] + (uint32_t)index], SB_TAG_INTEGER};
    return result;
}

void sb_store_index(uint64_t handle, uint64_t tag, int64_t index, uint64_t index_tag,
                    int64_t value, uint64_t value_tag) {
    if (value_tag != SB_TAG_INTEGER) sb_error_integer();
    if (index_tag != SB_TAG_INTEGER) sb_error_integer();
    uint32_t id = sb_validate_array(handle, tag);
    if (index < 0 || (uint64_t)index >= sb_array_length[id])
        sb_fail("Array index out of bounds", 25);
    sb_heap[sb_array_start[id] + (uint32_t)index] = (uint64_t)value;
}
