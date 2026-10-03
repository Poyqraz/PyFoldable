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
