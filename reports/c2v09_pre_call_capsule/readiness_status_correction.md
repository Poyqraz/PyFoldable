# Pre-call readiness status correction

The two persisted capsules stay byte-for-byte. This note does not rewrite them.

`reports/c2v09_pre_call_capsule/capsule.json` records the label `PRE-CALL READY FOR REVIEW`. That recorded label is not an accepted readiness result. Its canonical digest remains `78ab77bc4fdd75f6913f785bf86297d4be89903868fd5e0097975b4ce9b3eec1`.

`reports/c2v09_pre_call_capsule/loaded_correspondence_capsule.json` also records `PRE-CALL READY FOR REVIEW`. That recorded label is not an accepted readiness result. Its canonical digest remains `201c8a6e5535499dd5f00caaab6a721b0fcaa98955b653ecfc7dcb2001e0661a`.

The loaded-correspondence capsule's `xcr0_read_permitted` range records a direct call at offset 7 with opcode `e8`. The loaded bytes are `f30f1efa89f8c1e81b83e001c3`. Offset 7 is `c1 e8 1b`, which is `shr eax, 0x1b`, not a call. The byte scanner invented that edge. A matched export of those bytes does not establish a consumed call.

A later capsule records the corrected unresolved list. `PRE-CALL READY FOR REVIEW` is not produced by emptying that list.

That later record is `reports/c2v09_pre_call_capsule/boundary_decode_capsule.json`, canonical SHA-256 `4dda74eb4f37b9e9149190bde99433e33f66637a48595f516f2b51a892b90c7b`, from implementation `be76a8e5c551609a5addb4db9c3578e222741fe1`, tree `3f94775363330741e45658708e165f91f7375cd4`. Its label is `UNRESOLVED PRE-CALL HYPOTHESES`. The unresolved rows are interpreter binary64 arithmetic and storage semantics, `PyFloat_AsDouble` conversion semantics, and selected nextafter semantics. `authorizes_execution` is false.
