# Pre-call readiness status correction

The two persisted capsules stay byte-for-byte. This note does not rewrite them.

`reports/c2v09_pre_call_capsule/capsule.json` records the label `PRE-CALL READY FOR REVIEW`. That recorded label is not an accepted readiness result. Its canonical digest remains `78ab77bc4fdd75f6913f785bf86297d4be89903868fd5e0097975b4ce9b3eec1`.

`reports/c2v09_pre_call_capsule/loaded_correspondence_capsule.json` also records `PRE-CALL READY FOR REVIEW`. That recorded label is not an accepted readiness result. Its canonical digest remains `201c8a6e5535499dd5f00caaab6a721b0fcaa98955b653ecfc7dcb2001e0661a`.

The loaded-correspondence capsule's `xcr0_read_permitted` range records a direct call at offset 7 with opcode `e8`. The loaded bytes are `f30f1efa89f8c1e81b83e001c3`. Offset 7 is `c1 e8 1b`, which is `shr eax, 0x1b`, not a call. The byte scanner invented that edge. A matched export of those bytes does not establish a consumed call.

A later capsule records the corrected unresolved list. `PRE-CALL READY FOR REVIEW` is not produced by emptying that list.
