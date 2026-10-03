#include <stdint.h>
#include <cpuid.h>
void read_state(uint32_t *out) {
 __asm__ volatile("stmxcsr %0" : "=m"(out[0]));
 unsigned short cw; __asm__ volatile("fnstcw %0" : "=m"(cw)); out[1]=cw;
 unsigned a,b,c,d; __cpuid_count(1,0,a,b,c,d);out[2]=a;out[3]=b;out[4]=c;out[5]=d;
 __cpuid_count(7,0,a,b,c,d);out[6]=a;out[7]=b;out[8]=c;out[9]=d;
 if (c & (1u << 27)) {
  unsigned lo,hi; __asm__ volatile("xgetbv" : "=a"(lo),"=d"(hi) : "c"(0));out[10]=lo;out[11]=hi;
 }
}
