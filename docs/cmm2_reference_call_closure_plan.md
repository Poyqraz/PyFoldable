# Reference-call closure plan

Status: **PROPOSED / NOT ESTABLISHED / NOT AN ADMISSION**.

This document plans one later evidence packet. It does not capture a process,
change a validator, or admit readiness. `accept()` stays closed. Candidate29
stays **NOT SELECTED**. `eligibility_evidence`, `physical_qualification`, and
`authorizes_execution` stay false. Overall preservation stays `NOT ESTABLISHED`.

Plan baseline: head `d1fe839faf952f79db855d4852be629099c608d0`, tree
`833f7a1361ebc518ba5a88f59e9e8bdd7f01c153`. The partial-width LEA repair at
that head stays closed. Accepted inventory and correspondence validators stay
unchanged.

## Evidence used

The enumeration below is the archived observation
[reference_call_evidence.json](../reports/c2v09_pre_call_capsule/reference_call_evidence.json).

| Field | Value |
| --- | --- |
| File SHA-256 | `99d4304fab2a174f83cd45203f739811e33ff18abb522de17cefbfb7d2672664` |
| Canonical digest | `00364c0abd0feedbf0e3b670f443558b8805abafe91807e2ba618e1a12c08699` |
| Measurement head / tree | `f0b9a990e221121ea3786c2e0b0c6c66b278fcdf` / `35ec8d503f7b69941680e99d69af8645e98334ce` |
| Process | pid 64409, `LD_BIND_NOW=1`, image `/usr/bin/python3.12` |
| Callee prefix | `0x611480`, 2556 bytes, file match, `complete_prefix` |
| Dossier status | `NOT ESTABLISHED`, `preservation_established` false |

Addresses in that file identify the archived process. A later capture has to
resolve its own image. The eleven observation files stay byte-for-byte.

Reachability in the sections below is a reading of those stored callee and
stub bytes: direct branch targets, fallthrough, stop at `ret`, and no entry
into a call target. It is the same captured map the observation walked. It is
not a new runtime capture.

## What already has to survive

The constructor call at `0x556161` leaves `r14` and `rbx` live. The callee
prologue records both pushes while those values are still `entry`:

| Instruction | Address | Slot after `mov rbp, rsp` |
| --- | --- | --- |
| `push r14` | `0x61148a` | `[rbp - 0x10]` |
| `push rbx` | `0x611490` | `[rbp - 0x28]` |

The prologue then executes `sub rsp, 0x18`. On the captured paths that reach a
child call, the only `rsp` adjustments before the epilogue are those pushes
and that `sub`. At each such call, before the call instruction pushes the
return address, `rsp = rbp - 0x40`. After that push, the `r14` slot is
`[rsp + 0x38]` and the `rbx` slot is `[rsp + 0x20]` relative to the child
entry.

The epilogue at `0x61180a` is `add rsp, 0x18`, `mov eax, ebx` at `0x61180e`,
then `pop rbx`, `pop r12`, `pop r13`, `pop r14`, `pop r15`, `pop rbp`, `ret`.
The pops reload the slots. Reachable instructions also write the `r14` and
`rbx` registers, including `mov rbx, rdi` at `0x6114d1` and
`mov r14d, dword ptr [rip + 0x525941]` at `0x611550`. Those register writes
are not on every path to every call, and they are not the values the epilogue
returns. The qwords in the two slots are what have to survive.

Captured `[rbp]` accesses reachable from `0x611480` name `[rbp - 0x40]` and
`[rbp - 0x38]` only. Those are the three-qword scratch area below the `rbx`
slot. The decoded reachable bytes contain no store to `[rbp - 0x10]` or
`[rbp - 0x28]`. That scan does not prove the slots survive: the walker treats
a `[rbp]` operand as unmodeled, and a child can still store through the
incoming stack pointer.

The recorded returns are both at `0x61181a`. One is `r14=entry`, `rbx=entry`,
`broken` false. The other is `r14=other`, `rbx=other`, `broken` true. The only
captured transfer into `0x61180a`, besides fallthrough from `call 0x6104b0` at
`0x611805`, is `jmp 0x61180a` at `0x4bca3c`. That jump is the cold stub
`or ebx, 0xffffffff` reached by `je 0x4bca39` at `0x61149d`. The `or` writes
the `ebx` register. The following pop reloads the slot. A path that executes
`0x611805` is already broken by that call, so the recorded non-broken return
is the cold edge.

## Flag dword

`0x611495` is `mov eax, dword ptr [rip + 0x5259f9]`. The effective address is
`0xb36e94`, the same dword recorded for the `_Py_NewReference` test. The
observation's loaded bytes are `00000000`, with `selects_future_branch` false.
`0x61149d` is `je 0x4bca39` on that test. `_Py_NewReference` uses `jne` on the
same address to reach this callee.

A stored zero does not choose either future branch. Excluding the cold edge,
or excluding the hot edge, would require a separate proof that every write to
`0xb36e94` between `0x583d14` and `0x611495` is accounted for in the same
thread, and that the value at the first test is still the value at the second.
That write-set is not in the observation. Both edges stay in the captured
graph.

## Sixteen child calls

The observation records these 16 calls. All 16 are reachable from `0x611480`
in the stored map. Each fallthrough has a captured path to `0x61181a`. That is
existence of a path, not a claim that every execution returns.

| Site | Bytes | Target | Form |
| --- | --- | --- | --- |
| `0x6114db` | `e8b0ebffff` | `0x610090` | direct |
| `0x6114ea` | `e801b0feff` | `0x5fc4f0` | direct |
| `0x61150b` | `e8806dffff` | `0x608290` | direct |
| `0x611590` | `e80b67feff` | `0x5f7ca0` | direct |
| `0x6115c8` | `ff5018` | unresolved | `call qword ptr [rax + 0x18]` |
| `0x61169c` | `e81f28f7ff` | `0x583ec0` | direct |
| `0x6116d5` | `e8e627f7ff` | `0x583ec0` | direct |
| `0x61170d` | `e8ae27f7ff` | `0x583ec0` | direct |
| `0x611745` | `e87627f7ff` | `0x583ec0` | direct |
| `0x611787` | `e83427f7ff` | `0x583ec0` | direct |
| `0x6117df` | `ff5018` | unresolved | `call qword ptr [rax + 0x18]` |
| `0x611805` | `e8a6ecffff` | `0x6104b0` | direct |
| `0x61184f` | `ff157b565200` | unresolved | `call qword ptr [rip + 0x52567b]` |
| `0x611866` | `e8a505e1ff` | `0x421e10` | direct |
| `0x611877` | `e8b4adfeff` | `0x5fc630` | direct |
| `0x6118f5` | `e836adfeff` | `0x5fc630` | direct |

Repeated resolved targets, with every site kept:

| Target | Sites |
| --- | --- |
| `0x583ec0` | `0x61169c`, `0x6116d5`, `0x61170d`, `0x611745`, `0x611787` |
| `0x5fc630` | `0x611877`, `0x6118f5` |
| `0x610090` | `0x6114db` |
| `0x5fc4f0` | `0x6114ea` |
| `0x608290` | `0x61150b` |
| `0x5f7ca0` | `0x611590` |
| `0x6104b0` | `0x611805` |
| `0x421e10` | `0x611866` |

The three unresolved indirect sites are `0x6115c8`, `0x6117df`, and `0x61184f`.
The first two share the encoding `call qword ptr [rax + 0x18]`. Sharing that
encoding does not mean they share a callee. `rax` is loaded from a different
rip-relative qword before each site. `0x61184f` reads a different slot,
`[rip + 0x52567b]`.

The decoded window contains further `call` instructions, including `0x61193b`.
They are absent from `callee_events.outgoing_calls` and are not reachable from
`0x611480` in this map. They stay outside this plan.

## Four unresolved exits

| Exit | Captured predecessor | Edge | Captured successor | Rejoin |
| --- | --- | --- | --- | --- |
| `0x4bca05` | `jne 0x61160e` at `0x4bc9ff` | not-taken fallthrough | none | no captured bytes |
| `0x4bca15` | `js 0x6115e1` at `0x4bca0f` | not-taken fallthrough | none | no captured bytes |
| `0x4bca41` | `js 0x4bca41` at `0x61187e` | taken target | none | no captured bytes |
| `0x4bca63` | `jne 0x611660` at `0x4bca5d` | not-taken fallthrough | none | no captured bytes |

Stub entries that reach those predecessors:

| Predecessor | Entered from |
| --- | --- |
| `0x4bc9f8` (`mov rbx, [rbx+8]`; `test`; `jne`) | `jmp 0x4bc9f8` at `0x61156f` and `0x611910` |
| `0x4bca0a` (`mov rax, [rsi]`; `test`; `js`) | `js 0x4bca0a` at `0x611900`, after `call 0x5fc630` at `0x6118f5` |
| `0x61187e` | `test eax, eax` at `0x61187c`, the fallthrough of `call 0x5fc630` at `0x611877` |
| `0x4bca56` (`mov rbx, [rbx+8]`; `test`; `jne`) | `je 0x4bca56` at `0x611649` |

The taken or not-taken side that stays inside the map can still reach
`0x61181a`. The side named above leaves the capture. No recorded flag covers
these conditions. They stay unresolved.

## Route groups

### Direct target `0x583ec0` (five sites)

Slots that must survive are the two entry qwords above. By these sites the
body has already executed reachable `r14` and `rbx` register writes; the
epilogue still reloads the slots. Each fallthrough can reach `0x61181a`.
Captured evidence is the call displacement and the surrounding bytes. Missing
evidence is the target image: file match, instruction coverage, its own calls,
and any store through the incoming `rsp`. One prefix of `0x583ec0` would bind
all five sites. Its children would remain unresolved.

### Direct target `0x5fc630` (two sites)

`0x611877` falls through to `test eax, eax` at `0x61187c` and `js 0x4bca41` at
`0x61187e`. The taken target `0x4bca41` is an unresolved exit. `0x6118f5`
falls through to `mov rsi, qword ptr [rbp - 0x38]` at `0x6118fa`, then
`test eax, eax` and `js 0x4bca0a` at `0x611900`. Both sides of that `js` are
in the captured map. The unresolved exit on the taken side is `0x4bca15`, the
not-taken fallthrough of `js 0x6115e1` at `0x4bca0f`. The in-map sides can
still reach the epilogue. The same two slots must survive. Missing evidence
is the target prefix. A capture of this body does not close `0x4bca41` or
`0x4bca15`.

### Single-site direct targets

| Target | Site | Rejoin already captured | Smallest missing piece |
| --- | --- | --- | --- |
| `0x610090` | `0x6114db` | fallthrough `0x6114e0` reaches the ret | one unread prefix |
| `0x5fc4f0` | `0x6114ea` | fallthrough `0x6114ef` reaches the ret | one unread prefix |
| `0x608290` | `0x61150b` | fallthrough `0x611510` reaches the ret; `je 0x4bca2f` returns to `0x61168b` | one unread prefix |
| `0x5f7ca0` | `0x611590` | fallthrough `0x611595` reaches the ret | one unread prefix |
| `0x6104b0` | `0x611805` | fallthrough is the epilogue at `0x61180a` | one unread prefix |
| `0x421e10` | `0x611866` | fallthrough `0x61186b` reaches the ret | one unread prefix |

`0x6104b0` is the shortest rejoin. Closing only that prefix would leave every
earlier call on the paths that reach `0x611805` unresolved. It is not the
selected packet.

### Indirect sites

`0x6115c8` and `0x6117df` call `[rax + 0x18]`. Nothing between the preceding
load and the call writes `rax`. The loads are `mov rax, qword ptr [rip +
0x52596f]` at `0x6115ba` (effective address `0xb36f30`) and `mov rax, qword
ptr [rip + 0x525764]` at `0x6117d5` (effective address `0xb36f40`). `0x61184f`
calls `[rip + 0x52567b]`. The observation does not contain those qwords, so
the stored instructions do not name the callees. These three sites stay
unresolved. This plan does not ask for an execution that materializes them.

## Conditional preservation argument

This paragraph is a conditional argument. It is not established evidence.

If a captured path reaches `0x61180a`, and every child call on that path
returns to its fallthrough, and none of those children store to the caller's
`[rsp + 0x20]` or `[rsp + 0x38]` at their entry, then the epilogue pops reload
the entry qwords. The cold edge `0x4bca3c` has no child call; its pop reload
is the recorded non-broken return. A hot path has the conjunction of every
child it actually entered. One child that does not return, or one unresolved
exit, leaves that path unresolved. The argument does not need every child to
terminate on every input, and it does not need allocator internals. It needs
the children that do return to leave those two qwords unchanged.

The current walker marks the path broken at the call and does not apply the
later pops. The recorded `entry` return is the path that never executes a
call. The conditional argument is the reason a later packet could reconnect a
returning child to those pops. The packet below does not complete that
conjunction.

## ABI label and self-issued receipt

The System V AMD64 psABI classifies `rbx` and `r14` as callee-saved registers
at `ret`. That classification applies only when all of the following are
bound to the same artifact: the ELF is the x86-64 SysV image under analysis,
the callee bytes are the bytes compiled for that convention, and the claim is
limited to register values at `ret`. It does not by itself say that the
caller's spill slots at `[rsp + 0x20]` and `[rsp + 0x38]` are unmodified,
because that is a statement about stores, and the psABI text is not attached
to these hashes.

The observation records the assumption "no ABI callee-saved rule is used".
That sentence, and any later note that repeats it, is a self-issued receipt.
The correction record already requires an approval binding outside the
supplied claim. Neither the psABI name nor that receipt clears preservation.

A callee contract that could be used later is a byte-level statement for one
target hash: its captured prefix returns to the fallthrough, and its decoded
stores do not write the incoming frame above the return address, with every
child call inside that prefix left unresolved. That contract has to be
reviewed against those bytes. It is planned work, not this document.

## Selected next packet

Packet: **one unread prefix of archived direct target `0x583ec0`**.

This is the only resolved target shared by more than two of the 16 sites.
One prefix binds five site identities. It is smaller than capturing all eight
direct targets, and it does not pretend that the epilogue is locally closed.

Acceptance criteria for that later packet:

1. A new observation file. The eleven current observation files stay
   byte-for-byte.
2. One `LD_BIND_NOW=1` process. The capture reads bytes. It does not call
   `0x583ec0`, `_Py_NewReference`, or `PyFloat_FromDouble`.
3. The target address is resolved in that process from the call displacement
   at one of the five sites. The archived address is a label for this plan,
   not the evidence that the new process mapped it.
4. The record includes loaded bytes, file match, instruction-boundary
   coverage, and the outgoing calls inside the prefix. Those calls stay
   unresolved. The prefix stops at a fixed bound or at the first incomplete
   decode.
5. `preservation_established` stays false. `accept()` stays closed.
   Candidate29 stays **NOT SELECTED**. The three authority flags stay false.
6. The flag dword is not used to drop a branch. The four exits and the other
   call targets stay unresolved.

Scope limits: no recursive walk into the prefix's children, no new symbolic
executor, no allocator or failure-sibling work, no change to the accepted
validators, no ABI clearance, and no claim that the five sites preserve
`r14` or `rbx`.

## Separated claims

| Kind | Claim |
| --- | --- |
| Established | The observation lists these 16 calls and 4 exits. The prologue pushes entry `r14` and `rbx`. The reachable decoded bytes do not name stores to `[rbp - 0x10]` or `[rbp - 0x28]`. The non-broken return is the cold edge into `0x61180a`. Preservation is `NOT ESTABLISHED`. |
| Conditional | If every child that returns leaves the two entry slots unchanged, the epilogue pops reload them. The conjunction is open. |
| Planned | A later non-executing prefix of `0x583ec0` can bind the five sites. It does not establish preservation. |
