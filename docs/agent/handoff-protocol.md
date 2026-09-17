# Agent onboarding and task handoff

Start with [AGENTS.md](../../AGENTS.md), then [current state](current-state.md),
the relevant architecture/decision and source/tests. A conversation, Repomix dump
or generated export is temporary analysis input, never canonical project memory.

## Resume protocol

1. Inspect `git status --short`, branch, HEAD and remote base. Fetch before deciding
   what remains; compare open/merged PRs and actual diff. Preserve unrelated edits.
2. Read the latest handoff if one exists; verify its SHAs against git. A task title,
   old plan or screenshot of a timeout does not prove work is incomplete.
3. Follow the relevant public entry point through implementation and tests. Treat
   code/tests as authoritative; record contradictory docs in current-state drift.
4. Define a bounded slice, explicit exclusions and acceptance tests. Check that the
   capability is not already implemented elsewhere. Document a proposed scope as
   proposed until implemented; never infer approval from a TODO.
5. Work under the [development contract](../development/commands.md). Independent
   reviewers must inspect the final code, not merely repeat the implementer's summary.
6. At a pause, save a compact task checkpoint in the task branch/PR and, when needed,
   `docs/agent/handoffs/<task>.md`. Commit valuable unshipped work before a disposable
   environment is lost; do not rely on local untracked logs. Never commit secrets.

## Checkpoint template

```markdown
# Task Handoff: <id and bounded goal>

Goal:
Code base commit:
Branch / current commit / tree:
PR and remote head:
Completed:
Remaining:
Important decisions and evidence paths:
Files changed:
Unrelated work to preserve:
Tests passed (command, result, tested SHA/tree):
Tests failing / skipped / not run (reason):
Independent review (reviewed SHA, findings, disposition):
GitHub CI / reviews (exact head, URLs, pending gates):
Known risks and evidence limits:
Unresolved questions:
Next recommended action:
Rollback (affected commits/artifacts; preserve unrelated work):
```

A checkpoint's commit may follow the implementation it describes: label the
**tested implementation SHA/tree** separately. A file cannot truthfully contain
its own future commit hash. Store only a summary and reproducible commands; link
durable CI/PR evidence instead of copying giant logs.

After merge, update the current-state snapshot when capability or priorities
change, and link the merged PR. Supersede unfinished handoffs explicitly. Keep
feature contracts authoritative for details; do not duplicate their numeric limits
across AGENTS, rules and status documents. Revert specific shipped commits for a
rollback; never reset away unrelated user changes.

## Cursor readiness: configuration decision

At the audited baseline no `.cursor/rules/`, `.cursor/skills/` or
`.cursor/environment.json` is tracked. The old AGENTS reference to a provisioned
update script was not backed by a repository script. A clone must follow the
explicit setup commands; no cloud credentials or vendor settings are assumed.

For this increment, **AGENTS is the only always-read project contract** and the
linked documents supply progressive disclosure. Do not add large vendor-specific
rule files that duplicate it. No new tool-specific environment schema or skills
are installed by this documentation change.

| Mechanism | Assessment / proposed use |
| --- | --- |
| Root AGENTS | Implemented: navigation, invariants, commands, review/Done contract |
| Scoped Cursor rules | Candidate only if repeated violations justify them: geometry/evidence changes must preserve unknown scope; UI changes must preserve explicit runs/invalidation. Already covered in AGENTS/tests, so no duplicate rules now |
| `repo-onboarding` skill | Not needed as a separate skill; this short resume protocol is tool-independent |
| `pr-readiness` skill | Worth extracting only when multiple tasks need executable automation for exact-head CI/review/tree checks; use this protocol today |
| `test-impact-analysis` skill | Defer; the commands guide already maps boundaries to tests |
| Cursor environment | Add only after verifying the actual cloud bootstrap interface and needed setup; do not guess a JSON schema or bake in machine paths |

If a dedicated skill is later created, keep procedural detail there and leave
rules short. If a special environment fails, report the real limitation rather
than claiming Cursor, Bugbot, a solver or a test ran. GitHub Bugbot does not replace
the separate reviewer. Existing contribution/CLA requirements still apply.
