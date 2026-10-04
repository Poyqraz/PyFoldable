#include <stdint.h>
#include <cpuid.h>

/* XGETBV faults unless CPUID.1:ECX.OSXSAVE[bit 27] is set.
   Leaf 7 ECX bit 27 is a different feature and must not be consulted.
   Slots 10 and 11 stay at their explicit initial value when XGETBV is not
   executed; that value is not an observation of XCR0. */
int xcr0_read_permitted(uint32_t leaf1_ecx, uint32_t leaf7_ecx) {
    (void)leaf7_ecx;
    return (leaf1_ecx & (1u << 27)) != 0u;
}

void read_state(uint32_t *out) {
    unsigned index;
    for (index = 0; index < 12u; index++)
        out[index] = 0u;
    __asm__ volatile("stmxcsr %0" : "=m"(out[0]));
    unsigned short control;
    __asm__ volatile("fnstcw %0" : "=m"(control));
    out[1] = control;
    unsigned eax, ebx, ecx, edx;
    __cpuid_count(1, 0, eax, ebx, ecx, edx);
    out[2] = eax;
    out[3] = ebx;
    out[4] = ecx;
    out[5] = edx;
    uint32_t leaf1_ecx = out[4];
    __cpuid_count(7, 0, eax, ebx, ecx, edx);
    out[6] = eax;
    out[7] = ebx;
    out[8] = ecx;
    out[9] = edx;
    if (xcr0_read_permitted(leaf1_ecx, out[8])) {
        unsigned lo, hi;
        __asm__ volatile("xgetbv" : "=a"(lo), "=d"(hi) : "c"(0));
        out[10] = lo;
        out[11] = hi;
    }
}
