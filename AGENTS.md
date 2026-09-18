# PyFoldable agent contract

## Purpose and orientation

Python research software for tip-hinged foldable propellers: numerical analysis,
geometry screening, evidence comparison and a Streamlit engineering workspace.
Software correctness is distinct from physical qualification of the prototype.

Read progressively; do not ingest the entire repository:

1. [Current state and known gaps](docs/agent/current-state.md).
2. [Task → file navigation map](docs/agent/navigation-map.md) when locating a change.
3. [Architecture, data and critical flows](docs/architecture/overview.md).
4. [Development commands and test selection](docs/development/commands.md).
5. Relevant source, tests and the linked feature contract.
6. [Decisions](docs/architecture/decisions.md) and
   [handoff protocol](docs/agent/handoff-protocol.md) when changing boundaries or resuming.
7. Dated independent re-audit (application tree unchanged since GEOM-04):
   [2026-09-18 onboarding audit](docs/agent/onboarding-audit-2026-09-18.md).

Evidence precedence: code → tests → schemas → CI → runtime configuration → docs
→ git history → conversation. Record conflicts; never turn plans into facts.

## Repository map and boundaries

- `pyfoldable/core/`: SI design schema, polars/BEM, motor coupling, evidence contracts.
- `pyfoldable/application/`: source-bound requests, budgets, reports and UI services.
- `pyfoldable/geometry/`: bounded surface/solid distance and continuous clearance.
- `pyfoldable/dynamics/`: legacy dynamics and the separate PY-05 transient workflow.
- `pyfoldable/visualization/`: schematics and 2.5D previews; not CAD/CFD results.
- `pythrust/`: bundled legacy propeller/propulsion compatibility slice.
- `apps/pyfoldable_dashboard.py`: Streamlit presentation and session state.
- `configs/`, `data/`, `tests/fixtures/`, `reports/`: distinct configuration,
  source, test and archived evidence roles. Examples also use ignored `outputs/`.

No application database, migrations, REST service, login or role model exists.
The UI calls Python services synchronously. Legacy `pyfoldable.models` and
canonical `core.models` are different contracts; do not merge them casually.

## Canonical commands

From the repository root, use one Python environment (Python >=3.10):

```bash
python -m venv venv
./venv/bin/python -m pip install -e ".[dev,plot,ui]"
./venv/bin/python -m pytest tests/ -q
./venv/bin/python -m streamlit run apps/pyfoldable_dashboard.py
```

Reuse an existing working environment. CI tests Python 3.10/3.11. No repository
lint, formatter or typecheck gate exists. See the command guide for syntax,
packaging, Windows, optional solvers and example pipeline prerequisites.
Do not assume an untracked Cursor update script or preinstalled environment exists.

## Architectural invariants and sensitive areas

- Explicit units enter the canonical parser; solver models use SI. Respect
  signed-angle frames; do not mix legacy and PY-05 conventions.
- Hashes identify content, not truth/authenticity. Preserve source, revision,
  solver/settings, units and operating-condition provenance together.
- Synthetic fixtures, literature context, meshes and CI do not qualify a project
  rotor, mechanism or structure. Keep failed/pending/unknown evidence visible.
- UI solves require explicit actions. Changed inputs invalidate results/downloads;
  uploaded drafts do not overwrite canonical evidence. Preserve navigation state.
- Preserve budgets, fail-closed bounds and incomplete coverage. GEOM-04 clearance
  does not automatically qualify GEOM-01 search candidates.
- Upload parsing, repository path containment, XFOIL execution and cache locks are
  trust boundaries. Never accept uploaded solver commands, weaken validation to
  pass tests, expose credentials or commit secrets.
- Preserve third-party rights. `data/propellers/apc_202602/` holds first-party
  synthetic fixtures, not redistributable APC measurements.

## Change protocol and Definition of Done

1. Inspect status/base and plan a bounded slice. Preserve unrelated work; PR #3 is
   separate. Read current code before following an old plan.
2. Behavior changes use TDD: observe a failing regression, implement, rerun affected
   tests. Documentation-only changes use evidence/link/command checks, not invented
   behavioral tests for prose.
3. Run a separate automated reviewer independent of implementation. Address its
   findings, verify fixes and update the relevant contract/status.
4. Check GitHub reviews last with successful CI for the exact PR head. Use Cursor
   Bugbot when available; Gemini is not a gate. Neither replaces independent review.
5. Follow [contribution requirements](CONTRIBUTING.md), including the CLA statement;
   never fabricate a person's agreement. Merge only after applicable gates pass.
6. Verify merged tree equals tested tree. Report tests, skipped checks and evidence
   limits. For unfinished work, commit a handoff with exact refs.

Never silently rescale measurements, fill missing geometry/materials, relax
qualification gates, replace archived reports with session results, or claim a
stale check covers a new commit. No broad refactor belongs in a documentation task.
