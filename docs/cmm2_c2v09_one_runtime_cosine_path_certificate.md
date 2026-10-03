# One-runtime Python cosine path certificate

Status: one observed call path. This is not eligibility evidence.
`physical_qualification=false`. Baseline CI does not establish eligibility.
Python 3.10 and Python 3.11 CI environments are not certified here.

The selected cosine target is the qword in the GOT slot used by this process's
`PyCFunction_GetFunction(math.cos)` PLT stub. An independent
`ctypes.CDLL(libm).cos` lookup is not that observation. A lazy PLT slot that
still points at the resolver is NOT ESTABLISHED; the concrete method is to
start the interpreter with `LD_BIND_NOW=1` and reread that slot.

The historical CPython wrapper address argument DOES NOT APPLY to any
executable other than the certificate's pinned binary. The changed Python
operation graph and the returned source object are not in this certificate.
No cosine value, source call, selection, seal, or trajectory is produced.

The historical certificate file is unchanged.

## Concrete observation

Committed checkout `f343a9b206b0169e96bf5e66548ee08d257c3806`, tree
`8ba778104fcb3fd0498948cc1c91924c75ac0494`, started with `LD_BIND_NOW=1`,
produced
[reports/c2v09_cosine_path_certificate/observation.json](../reports/c2v09_cosine_path_certificate/observation.json).
Its digest is outside the payload. Runtime load addresses in that file are
process-specific; the stable code identity is the ELF virtual address and the
body digest.

`/usr/bin/python3.12`, SHA256
`e50d468e8b0adfb05733f5b87b3cff34829c4a8c1aea50c865aa8bdfe4bb150f`,
CPython 3.12.3 GCC 13.3.0. `PyCFunction_GetFunction(math.cos)` is ELF
`0x62e430`. It calls `PyFloat_AsDouble`, then `call cos@plt` at `0x4207e0`,
then jumps to `PyFloat_FromDouble` on the ordinary path. The PLT slot is
`0xa293d8`. With binding forced, that qword is libm ELF `0x7bad0`.

The 341 loaded bytes at that target match historical body
`f7a54037fbab80cbbf5a2c6954284f47330d936b103a0beac05913b6b1949a02`.
All 13 referenced constants match. MXCSR is `0x1fa0` (nearest ties-to-even,
DAZ and FTZ off, exception masks set), `fegetround` is 0, and x87 control is
`0x37f`. CPUID leaf 1 ECX has AVX, FMA, and OSXSAVE set. XCR0 is `0x602e7`,
so the XMM and YMM bits required by the historical predicate are set. Exact
historical XCR0 `0xe7` does not match. Leaf 1 EBX differed across reads and
is not an identity.

The libm body argument **APPLIES** to this selected path under that predicate.
The historical CPython wrapper address argument **DOES NOT APPLY**: this is
not executable `fa67443527ed9647f760d807e2a38f26340757123e643c4639cf273ed15d5ea7`,
and this wrapper is not the certified `mov`/`jmp math_1` thunk.

In this process the independent libm symbol address happened to equal the GOT
qword. That equality is not the evidence. Loaded wrapper bytes match the ELF
bytes at `0x62e430`. The decoded PLT jump is `ff 25 f2 8b 60 00`. Probe source
SHA256 `8a8fe2c2b1eb60cea016acec26d50fdcd902ee33ec57b81efa6273cb7fb3aaba`.

## Historical observation limitations

`reports/c2v09_cosine_path_certificate/observation.json` stays historical
evidence from checkout `f343a9b206b0169e96bf5e66548ee08d257c3806` and tree
`8ba778104fcb3fd0498948cc1c91924c75ac0494`. It is not the repaired certificate.

Limitation: CPUID leaf 7 overwrites the register checked for OSXSAVE. OSXSAVE belongs to CPUID leaf 1 ECX, which that probe had already stored. Leaf 7 ECX on that run was `0x1b415f5e`, so bit 27 happened to be set and XGETBV did execute. That coincidence is not proof the guard was correct.

Limitation: a skipped XGETBV left its output slots unwritten. The Python buffer is zeroed first, so an unavailable XCR0 could be published as register zero.

Limitation: the libm body argument was calculated before the loaded wrapper bytes were compared with the ELF bytes used for disassembly. Those bytes matched in this run, so the APPLIES result was not produced from a mismatch. The match was not a prerequisite.

## Repaired observation

Checkout `319c10ae22e55891ad8552d8741664c8ef7f7f38`, tree
`fff000b4c4bc9c7a4d64a5b3030f675ee3ede3fb`, started with `LD_BIND_NOW=1`, produced
[reports/c2v09_cosine_path_certificate/repaired_observation.json](../reports/c2v09_cosine_path_certificate/repaired_observation.json).
Checkout, tree, probe, and implementation are separate identities:

- checkout `319c10ae22e55891ad8552d8741664c8ef7f7f38`
- tree `fff000b4c4bc9c7a4d64a5b3030f675ee3ede3fb`
- probe `e75b6d88b78250ae9e4cce87839291c0540f018550dc14465409f7e12426d33d`
- implementation `5b4ed333d7d28c8606b59630cc17fee3a48b4a2af54fbf6051ad43c50e55c6bc`

XGETBV runs only when CPUID leaf 1 ECX OSXSAVE is set. A missing or mismatched loaded wrapper blocks attribution of the disk PLT/GOT path; the GOT qword can remain a raw observation. `eligibility_evidence` and `physical_qualification` stay false.

`/usr/bin/python3.12`, SHA256 `e1efa562c2cc2e35521a5c9c9b9939921001ff8ca9708a13ef15ace68cc2ccd7`, CPython 3.12.3 GCC 13.3.0. This executable is neither the historical pinned binary nor the binary in the historical observation. `PyCFunction_GetFunction(math.cos)` is ELF `0x62e890`. It calls `PyFloat_AsDouble`, then `call cos@plt` at `0x4207e0`. The PLT slot is `0xa283d8`. With binding forced, that qword is libm ELF `0x7bad0`.

The 341 loaded bytes match historical body `f7a54037fbab80cbbf5a2c6954284f47330d936b103a0beac05913b6b1949a02`. MXCSR is `0x1fa0`, `fegetround` is 0, and x87 control is `0x37f`. CPUID leaf 1 ECX has AVX, FMA, and OSXSAVE set. XCR0 is observed `0x602e7`, so the required XMM and YMM bits are set. Exact historical XCR0 `0xe7` does not match. Leaf 1 EBX is not an identity.

Loaded wrapper bytes match the ELF bytes at `0x62e890`. The decoded PLT jump is `ff 25 f2 7b 60 00`. The libm body argument **APPLIES** to this selected path. The historical CPython wrapper address argument **DOES NOT APPLY**. The independent libm symbol happened to equal the GOT qword. That equality is not the evidence. `physical_qualification=false`. This is not eligibility evidence.

If the GOT still points at the PLT resolver, the selected target is missing.
Obtain it by starting the same interpreter with `LD_BIND_NOW=1` and rereading
slot `0xa293d8`. Do not substitute `ctypes.CDLL(libm).cos`.
