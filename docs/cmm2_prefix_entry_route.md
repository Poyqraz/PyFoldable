# Entry route of the associated prefix

Status: **PROPOSED / NOT ESTABLISHED / NOT AN ADMISSION**.

This note reads one archived prefix. It does not capture a process, change a
validator, or admit readiness. `accept()` stays closed. Candidate29 stays
**NOT SELECTED**. `eligibility_evidence`, `physical_qualification`, and
`authorizes_execution` stay false. Preservation stays `NOT ESTABLISHED`.

The thirteen observation files stay byte-for-byte. Accepted validators,
admission repairs, the [closure plan](cmm2_reference_call_closure_plan.md),
the correction history, and the frozen numerical allowances stay unchanged.
The 256-byte figure below is a capture limit for one unread prefix. It does
not amend a frozen allowance.

## Evidence used

The bytes below are the archived observation
[reference_call_prefix_associated.json](../reports/c2v09_pre_call_capsule/reference_call_prefix_associated.json).

| Field | Value |
| --- | --- |
| File SHA-256 | `f7d9b24afc7b1e1d6f5be52ceef8d08f99687f528b7f3198f4fa7a9a8143a967` |
| Canonical digest | `6f1cc5005013f8f58dac6b865315f4bb6a5675c611e4ecda67a6bb9e67cdc994` |
| Measurement head / tree | `a207139cf7f93480780925d04e3ed4cde83ed521` / `841da5425927d6f26022bc222d01f0bea1429305` |
| Record head / tree | `a89bdda21959ffa01175f9009c458acef8575c69` / `cd913bd4155993ee69968757bf1ae1db31ce680a` |
| Process | pid 82926, thread `82926`, `LD_BIND_NOW=1`, image `/usr/bin/python3.12` |
| Entry | `0x583ec0`, the shared target of the five recorded edges |
| Coverage | 256 bytes captured, 255 decoded, trailing byte `48` incomplete |

The digest sits outside the payload. Addresses in the file identify that
archived process. A later capture has to bind its own image. The probe
receipt in the same file records the measuring probe image. Its pointers are
not the tail target of this entry.

The five recorded caller edges, labels only, are `e81f28f7ff` at `0x61169c`,
`e8e627f7ff` at `0x6116d5`, `e8ae27f7ff` at `0x61170d`, `e87627f7ff` at
`0x611745`, and `e83427f7ff` at `0x611787`. Each recorded target is
`0x583ec0`. Those historical addresses do not bind a later process.

## Decode

The complete range is `[0x583ec0, 0x583fbf)`. That is 255 bytes and 77
instructions. The captured byte at `0x583fbf` is `48`. It is not an
instruction. The last complete instruction is `mov rax, qword ptr [rbx + 0x98]`
at `0x583fb8`, and it ends at `0x583fbf`.

The entry walk follows fallthrough and a direct branch only when the
destination is an instruction in the complete range. It stops at a `ret`, at
an indirect jump, and at a direct target outside that range. It does not
follow a `call`. Padding, `endbr64`, and a prologue are decoded instructions.
They do not assign those bytes to a function.

## Entry-reachable instructions

Fourteen instructions are reachable from `0x583ec0` under that walk.

| Address | Bytes | Instruction | `rsp` after | `rbp` after |
| --- | --- | --- | --- | --- |
| `0x583ec0` | `f30f1efa` | `endbr64` | `S` | incoming |
| `0x583ec4` | `55` | `push rbp` | `S-8` | incoming |
| `0x583ec5` | `4889e5` | `mov rbp, rsp` | `S-8` | `S-8` |
| `0x583ec8` | `4154` | `push r12` | `S-0x10` | `S-8` |
| `0x583eca` | `53` | `push rbx` | `S-0x18` | `S-8` |
| `0x583ecb` | `4c8b6708` | `mov r12, qword ptr [rdi + 8]` | `S-0x18` | `S-8` |
| `0x583ecf` | `4889fb` | `mov rbx, rdi` | `S-0x18` | `S-8` |
| `0x583ed2` | `498b442478` | `mov rax, qword ptr [r12 + 0x78]` | `S-0x18` | `S-8` |
| `0x583ed7` | `4885c0` | `test rax, rax` | `S-0x18` | `S-8` |
| `0x583eda` | `0f846b9dedff` | `je 0x45dc4b` | `S-0x18` | `S-8` |
| `0x583ee0` | `5b` | `pop rbx` | `S-0x10` | `S-8` |
| `0x583ee1` | `415c` | `pop r12` | `S-8` | `S-8` |
| `0x583ee3` | `5d` | `pop rbp` | `S` | incoming |
| `0x583ee4` | `ffe0` | `jmp rax` | `S` | incoming |

`S` is `rsp` at `0x583ec0`, before `endbr64`. Each `push` and `pop` in this
list is an 8-byte stack operation. `endbr64` does not change `rsp` or `rbp`.

The three pushes store the incoming `rbp`, `r12`, and `rbx` at `[S-8]`,
`[S-0x10]`, and `[S-0x18]`. After `mov rbp, rsp`, those slots are `[rbp]`,
`[rbp-8]`, and `[rbp-0x10]`. The following `mov r12` and `mov rbx` overwrite
the registers. They do not store to those slots. No entry-reachable
instruction between the pushes and the pops writes those three qwords. The
three pops reload those qwords. At `jmp rax`, `rsp` is `S` again and the
reloaded registers are the incoming `rbp`, `r12`, and `rbx`.

`rdi`, the qword at `[rdi+8]`, and the qword at `[r12+0x78]` are
runtime-loaded values. `rax` at the `test` and at the `jmp` is that loaded
qword. This note does not bind it. An archived pointer or flag snapshot is
not a future route.

## Two unresolved transfers on the entry route

The earliest entry-reachable instruction with an unresolved destination is
`je 0x45dc4b` at `0x583eda`.

Its bytes are `0f846b9dedff`. The instruction ends at `0x583ee0`. The rel32
is the signed little-endian value of `6b9dedff`, which is `-0x126295`
(`-1204885`). `0x583ee0 - 0x126295 = 0x45dc4b`. That address is outside
`[0x583ec0, 0x583fbf)`. The taken edge leaves the prefix with `rsp = S-0x18`
and with the three saved qwords still stored. The incoming `r12` and `rbx`
registers have already been overwritten. The taken edge is the edge on which
`rax` compared equal to zero. The comparison does not select the edge.

The fallthrough is the three pops and `jmp rax` at `0x583ee4`, bytes `ffe0`.
That `jmp` has no direct target and no fallthrough. It is the indirect tail
transfer. It is the second unresolved transfer, and only on the not-taken
edge. The byte after it, at `0x583ee6`, is the start of
`nop word ptr cs:[rax + rax]`. The tail jump does not enter that `nop`.

## Linear-window calls

The complete 255 bytes also decode four `call` instructions. None of them is
in the fourteen-instruction entry walk. The archived observation already
marks each `resolved: false`.

| Address | Bytes | Archived target | Entry-reachable |
| --- | --- | --- | --- |
| `0x583f1c` | `e85f2b0200` | `0x5a6a80` | no |
| `0x583f36` | `e835000000` | `0x583f70` | no |
| `0x583f5c` | `e85ffeffff` | `0x583dc0` | no |
| `0x583fb3` | `e868290200` | `0x5a6920` | no |

`0x583f70` lies inside the captured window. The bytes there decode as
`endbr64` and a prologue. That overlap is not a completed call, and it is
not an ownership assignment. `0x583dc0` is below the window. `0x5a6a80` and
`0x5a6920` are outside it. Other direct targets of the parent, the three
parent indirect sites, and the four original exits stay unresolved.

The linear window also decodes conditional branches and one `ret` that the
entry walk does not reach: `jne 0x45dca3` at `0x583f16`, `je 0x45dc9b` at
`0x583f27`, `js 0x583f4b` at `0x583f40`, `je 0x583f56` at `0x583f49`,
`ret` at `0x583f55`, `jmp 0x583f4b` at `0x583f64`, `je 0x45dcd6` at
`0x583f98`, and `jne 0x5841e0` at `0x583fa9`. `0x5841e0` is past the
incomplete trailing byte. Those instructions stay outside the entry route.

## What the tail would have to carry

On the not-taken edge, `jmp rax` leaves `rsp` at `S`. The original return
address is still the qword at `[S]`: this path has no `call`, and the `jmp`
does not push. If the tail callee returns to the original caller, the four
open obligations move with it.

1. **Continuation and caller `rsp`.** The tail `ret` has to land on the
   original caller's fallthrough, and caller `rsp` has to be the value from
   immediately before the original `call`. At the `jmp`, `rsp` is already the
   callee-entry value, 8 bytes below that pre-call value, with the return
   address at `[rsp]`.
2. **Frame registers the caller consumes after the return.** The three pops
   reload this prologue's incoming `rbp`, `r12`, and `rbx` before the `jmp`.
   The original caller's later use of its own frame, including `rbp`, is
   outside this prefix. That correspondence stays with the tail callee.
3. **Both complete spill qwords.** The closure plan names the caller's
   `[rbp-0x10]` and `[rbp-0x28]`. At child entry those are `[S+0x38]` and
   `[S+0x20]`. The entry-reachable pushes write `[S-8]`, `[S-0x10]`, and
   `[S-0x18]` only. Those ranges do not overlap the two spill qwords. The
   tail callee still has the noninterference obligation, including a partial
   overlap and a transitive write.
4. **Later caller stores.** No entry-reachable instruction stores through a
   returned pointer. A value or pointer the tail callee leaves for a later
   caller store still has to be shown not to write either spill qword.

The taken edge does not reach `jmp rax`. Its own `rsp` is `S-0x18`, and its
three saved qwords are still on the stack. Restoring the original caller from
that edge is a separate obligation. This note does not discharge either edge.
No ABI callee-saved rule is applied.

## Selected next packet

Packet: **one unread prefix, at most 256 bytes, of the taken target of the
entry `je` at the bound current instruction whose bytes are `0f846b9dedff`.**

The archived target `0x45dc4b` is a label from this file. The read uses the
target computed in the later process. This note does not perform that read.

Applicability bindings, all required:

1. One `LD_BIND_NOW=1` process and one thread. The capture reads bytes. It
   does not call the target, the tail, `_Py_NewReference`, or
   `PyFloat_FromDouble`.
2. The entry is the shared target of the five current edges with labels
   `e81f28f7ff`, `e8e627f7ff`, `e8ae27f7ff`, `e87627f7ff`, and `e83427f7ff`,
   each bound on its own instruction boundary under the existing five-site
   rules. The archived addresses are not that binding.
3. From that entry, the decoded fallthrough reaches one `je` whose exact
   bytes are `0f846b9dedff`, whose end is `address + 6`, whose displacement
   is the signed rel32 of those bytes, and whose target is
   `address + 6 + displacement`. The six bytes match the file image. The
   recorded pid, thread, and image of that capture are the capture context.
4. The read is at most 256 bytes at that computed target. The record states
   captured length, decoded length, file match, and any incomplete trailing
   instruction. A shorter capture stays explicit. Calls inside that prefix
   stay unresolved.
5. The not-taken fallthrough and `jmp rax` stay unresolved. The four
   linear-window calls, the other direct targets, the three parent indirect
   sites, and the four original exits stay unresolved.
6. The loaded qwords that produced `rax`, and any archived pointer or flag
   snapshot, are not a route binding and are not a reason to drop either
   edge of the `je`.

The packet does not establish preservation. `accept()` stays closed.
Candidate29 stays **NOT SELECTED**. The three authority flags stay false.

## Separated claims

| Kind | Claim |
| --- | --- |
| Established | The 255 complete bytes decode as 77 instructions. Fourteen are reachable from `0x583ec0` before an unresolved transfer. The taken `je` leaves at `0x45dc4b` with `rsp = S-0x18`. The not-taken edge pops the three saved qwords and tail-jumps through `rax` with `rsp = S`. The four linear-window calls are outside that walk. Preservation is `NOT ESTABLISHED`. |
| Conditional | If the tail callee returns to the original caller, the four obligations above move with that return. The conjunction is open. The taken `je` is a separate exit and does not reach the tail. |
| Missing | The taken target, the tail body, the value of `rax`, the four linear-window calls, the other direct targets, the three parent indirect sites, and the four original exits are unresolved. The trailing `48` is incomplete. |
| Planned | One later non-executing read of at most 256 bytes can be taken at the bound `je` target after the applicability bindings hold. That read is not this document. |
