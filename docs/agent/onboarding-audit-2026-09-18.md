# Independent repository onboarding audit

**Audit date:** 2026-09-18
**Inspected HEAD:** `d7afc391d5f41b15259826b99a5ed7560153439e` (main, PR #64)
**Application-code baseline:** unchanged since `ca81d2d2b19622d65453e269d7bfcb48e70aec32` (GEOM-04, PR #63)
**Auditor role:** independent of the 2026-09-17 documentation increment
**Scope:** read-only comprehension; no application, schema, auth, or infrastructure change

`git diff --stat ca81d2d..d7afc39` is ten documentation files only. Application
behavior at this HEAD equals the GEOM-04 tree. Recheck git before treating this
file as current.

Evidence precedence used: code → tests → schemas/contracts → CI → runtime
config → docs → git history.

---

## 1. Executive repository summary

PyFoldable is a **Python scientific library** (setuptools package `pyfoldable`
0.3.0) plus **one Streamlit engineering workspace** and a **bundled PyThrust
compatibility slice** in the same distribution (`pyproject.toml`,
`apps/pyfoldable_dashboard.py`, `pythrust/`). It analyses tip-hinged foldable
propeller geometry, polars/BEM, mechanism transients, and evidence contracts.

It is **not** a hosted product: no database, ORM, migrations, REST API, login,
authorization, worker queue, broker, cloud storage, analytics pipeline, or
deployment IaC exist in the repository. API boundaries are Python functions,
dataclasses, and versioned TOML/JSON files.

Software correctness is distinct from physical qualification of a prototype.
`configs/ui/dashboard.toml` currently binds PR-06C to `blocked`, PR-06D to
`screening_only`, and PR-07/08/09/10 to `pending`.

---

## 2. Product mental model

**Actors:** researchers/engineers operating a trusted local checkout (CLI or
Streamlit). There is no end-user account model.

**Core loop:** edit or import geometry → bind sources/hashes → run an explicit
numerical action → inspect fail-closed diagnostics → compare against versioned
evidence → do **not** promote hashes into physical truth.

**Project targets (requirements, not measured results):** 250 mm open / 140 mm
stowed envelope and ≥0.85 thrust retention at 7100 RPM versus a matched
same-diameter reference (`configs/designs/TIP_HINGED_250_CANONICAL.toml`,
`docs/architecture/overview.md`). The 254 mm UIUC APC 10×4.7 fixture used by
PR-06D UI analysis is a **different** reference (`pyfoldable/application/analysis_run.py`).

**Historical V2 report numbers** in `README.md` (3.73 / 6.37 / 9.10 N at 7100
RPM) are archived model output in
`reports/foldable_v2_engineering_design/report_key_results.csv`, not a recomputed
BEM result.

---

## 3. Repository map

Not a JS/package-manager monorepo. One setuptools find (`pyfoldable*`,
`pythrust*`). Wheel data is only `pyfoldable/data/airfoils/*`; workspace
configs/reports/apps/tests are **checkout** artifacts (`pyproject.toml`).

| Path | Purpose | Owned responsibilities | Dependencies | Tests | Risk |
| --- | --- | --- | --- | --- | --- |
| `pyfoldable/core/` | Canonical SI models, polars, BEM, motor coupling, evidence contracts | Strict parse, fail-closed solvers, hashes | NumPy/SciPy; optional providers | `tests/core/` | High: units, provenance, qualification gates |
| `pyfoldable/application/` | UI-independent requests/artifacts | Drafts, searches, clearance, imports, dashboard snapshot | core, geometry, visualization, dynamics | `tests/application/` | High: private helper reuse, source identity |
| `pyfoldable/geometry/` | Bounded triangle/surface/solid distance | Exact predicates, hardware solids | application mesh semantics | `tests/geometry/` | High: numeric meaning of clearance |
| `pyfoldable/dynamics/` | Legacy V2 physics **and** PY-05 transient | Separate conventions; first-contact stop | core/application bindings | `tests/dynamics/` | High: mixed frames; skip-prone legacy |
| `pyfoldable/visualization/` | Schematics and 2.5D preview mesh | Not CAD/CFD | airfoil coordinates | `tests/visualization/`, `tests/test_visualization.py` | Medium: mesh changes alter clearance |
| `pyfoldable/providers/` | XFOIL subprocess, optional NeuralFoil | Local solver adapters | core provider contracts | `tests/providers/` | High: subprocess/exec trust |
| `pyfoldable/models.py`, `integration.py`, `performance.py`, … | Legacy V1/V2 JSON/CSV workflow | Distinct from `core.models` | `pythrust/` | `tests/test_integration.py`, `tests/test_performance.py` | High if merged casually |
| `pythrust/` | Bundled propeller/propulsion slice | Reference operating-point compatibility | NumPy | consumed by integration/legacy tests | Medium: incomplete vs upstream PyThrust |
| `apps/pyfoldable_dashboard.py` | Streamlit presentation (~1974 lines) | Session state, explicit buttons | application + visualization | `tests/ui/` | High: navigation/upload invalidation |
| `configs/` | Versioned designs, polars, dashboard gates | Manifest–evidence binding | loaded, not executed as code | dashboard/config tests | Medium |
| `data/` | First-party synthetic + literature metadata | Not APC redistribution | license tests | `tests/test_license_policy.py` | High: third-party rights |
| `tests/fixtures/` | Polar/rotor/CFD/experiment fixtures | Regression envelopes | CI | corresponding `tests/core/` | Medium |
| `reports/` | Archived evidence JSON/MD | Gate identities | dashboard.toml | evidence tests | High: do not overwrite with session results |
| `examples/` | CLI evidence/report scripts | Not a second product | checkout paths | some `tests/core/test_*_evidence.py` | Medium |
| `outputs/` | Ignored generated files | Example/runtime scratch | gitignore | skip if missing | Low |
| `venv/`, `pyfoldable.egg-info/` | Local/generated install | Not source | gitignore | n/a | Do not commit |

Generated/vendor: `venv/`, `*.egg-info/`, `__pycache__/`, `outputs/` (`.gitignore`).
No `node_modules`, no committed `.env`.

---

## 4. Architecture map

```
CLI examples ─┐
              ├─► application services ─► core / geometry / dynamics
Streamlit UI ─┤                         ─► visualization mesh
              └─► session state only
core ─► providers ─► optional local XFOIL/NeuralFoil + filesystem cache
application ─► configs / reports / fixtures (repo-contained paths)
```

This is a responsibility map, not a package-enforced DAG
(`docs/architecture/overview.md`). Streamlit also imports domain types directly
(`apps/pyfoldable_dashboard.py`).

| Subsystem | Responsibility | Primary paths | Inputs → outputs | Owned data | Invariants | Security |
| --- | --- | --- | --- | --- | --- | --- |
| Canonical config | Engineering units → SI `PropellerDesign` | `core/config.py`, `units.py`, `models.py` | TOML/JSON → frozen dataclasses | `configs/designs/` | Bare numbers rejected; finite SI | Parser is a trust boundary for files |
| Polar/BEM | Families, section loads, annulus/rotor | `core/polar_*.py`, `bem.py`, `bem_rotor.py`, `foldable_rotor.py` | tables + stations → loads/diagnostics | cache JSON under configured root | fail-closed bounds; section ≠ full BEM | cache errors ≠ solver success |
| Providers | Local polar generation | `providers/xfoil.py`, `neuralfoil.py`, `core/polar_config.py` | request → result/attempts/health | optional cache | lazy factories; capabilities | argv subprocess, no `shell=True` |
| Motor coupling | Electrical vs shaft equilibrium | `core/motor_bem_coupling.py` | motor + BEM → operating point | reports/PR-07 JSON | does not rewrite V2 table | n/a |
| Application requests | Explicit prepare/run, hashes | `application/*.py` | draft/upload → artifact JSON | session / download | rehash before run | bounded uploads |
| Geometry screening | Hinge/stow + clearance | `application/geometry_search.py`, `surface_clearance.py`, `geometry/` | draft + budgets → ledger | none persisted | unknown stays unknown | hardware JSON not CAD exec |
| PY-05 dynamics | Prescribed-drive ODE to first contact | `dynamics/mechanism_transient.py`, `application/mechanism_transient.py` | drive/mass JSON → history | session | no bounce/latch/BEM feedback | JSON size/schema |
| Evidence gates | Manifest must match archived JSON | `application/dashboard.py`, `configs/ui/dashboard.toml` | repo paths → snapshot | reports/*.json | path containment; qualified requires `passed=true` | `_inside_repo` |
| UI | Turkish workspace | `apps/pyfoldable_dashboard.py` | widgets → session | Streamlit session | explicit buttons; invalidate on change | maxUploadSize 5 MB |
| Legacy V1/V2 | Kinematics, calibrated split, reports | package-root modules + `dynamics/physics_*.py` | V02 JSON → CSV/report | `reports/foldable_v2_*` | distinct models | synthetic APC dir naming |

No persistence layer beyond files. No authn/authz layer. No analytics product.
Observability is report diagnostics, provider health, and CI artifacts.

---

## 5. Data model

**There is no database.** Conceptual entities are frozen dataclasses and
versioned files.

| Entity | Purpose | Relationships | Lifecycle | Permissions | Constraints |
| --- | --- | --- | --- | --- | --- |
| `PropellerDesign` | Canonical SI design | blade, airfoils, hinge, conditions, optional motor/material | loaded from TOML; drafts are copies | operator filesystem | unique airfoil/condition ids; hinge inside radius (`core/models.py`) |
| `DesignDraftArtifact` | Unqualified editable draft | `artifact_class=unqualified_design_draft`; source SHA | rebuilt on edit; never writes canonical file | session/download | round-trip through `load_design_config` |
| `StationBundle` | Explicit measured/parametric stations | binds to diameter/hub/profile | apply/rebind | session | no silent physical rescale |
| Polar table/family | 2D aero tables | profile coordinates + Re/Mach grid | cache optional | local cache files | `physical_qualification` must stay false on uploads |
| `HardwareBundle` | Declared convex solids/cylinder | body-local frames; 1-based blade ids | upload persist + explicit clear | session | schema `pyfoldable.hardware.v1`; max 256 KiB / 16 bodies |
| `SurfaceClearanceRequest` | Interval clearance | draft + hardware + budgets | explicit run | session/download | `full_propeller_clearance` is always `None` |
| Mechanism request | PY-05 history | draft-bound mass optional | explicit run; stop at first contact | session | prescribed drive |
| Test-stand / FEA / CFD contracts | Evidence identity | matched revision/run/condition | archived reports; session inspect | no promotion on upload | canonical IDs in `evidence_import.py` |
| Dashboard gates | Project status | `dashboard.toml` ↔ `reports/*.json` | fail-closed load | none | expected_decision must equal JSON |

Hashes identify **content**, not authenticity (`docs/architecture/decisions.md`
ADR-001). Optional `MaterialModel` / `ManufacturingModel` fields are not
measured material evidence.

**Application vs store discrepancy:** none at the SQL/RLS layer (absent). The
real discrepancy is **UI/search assuming GEOM-04 exists while
`run_geometry_search` still sets `surface_path_clearance` / `interblade_clearance`
to `None`** (`pyfoldable/application/geometry_search.py`).

---

## 6. Critical workflows

### 6.1 Workspace bootstrap

`apps/pyfoldable_dashboard.py::main` → `load_dashboard_snapshot(REPO_ROOT)` →
`configs/ui/dashboard.toml` → `_inside_repo` for design and each
`evidence_path` → JSON `decision_key` must equal `expected_decision` → overview
metrics. No network, no DB. Tests: `tests/application/test_dashboard.py`,
`tests/ui/test_streamlit_dashboard.py`.

### 6.2 Geometry edit / draft / preview

`_render_design_geometry` → durable `_geometry_control_*` session keys →
`build_design_draft` (`application/design_draft.py`) → canonical parser via
tempfile → 2.5D `build_propeller_preview_mesh` → optional TOML download.
Canonical `configs/designs/TIP_HINGED_250_CANONICAL.toml` is not overwritten.
Station apply: `parse_station_bundle` / `audit_station_bundle`. Tests:
`tests/ui/test_geometry_navigation_ui.py`, `test_blade_stations_ui.py`,
`tests/application/test_design_draft.py`.

### 6.3 Active polar BEM and chord/twist search

Polar JSON upload (`application/polar_upload.py`, 2 MiB, nested-node budget,
`physical_qualification` must be false, coordinate SHA must match draft) →
explicit **Aktif taslağı BEM ile çalıştır** → `prepare_polar_run` /
`run_polar_run` → `run_design_analysis` → `solve_bem_rotor` for fully open
zero-offset geometry only. Search: `prepare_active_search` /
`run_active_search`, max 25 candidates / 400 annulus. Input change clears
session results. Tests: `tests/application/test_design_analysis.py`,
`test_polar_upload.py`, `test_active_design_search.py`,
`tests/ui/test_active_design_polar_ui.py`, `test_active_search_ui.py`.

### 6.4 GEOM-01 search vs GEOM-03/04 clearance (intentionally separate)

Search: `prepare_geometry_search` → `run_geometry_search` → mesh/audit
constraints; `surface_path_clearance` and `interblade_clearance` remain `None`.
Candidate details set `surface_path_clearance_status` to
`unknown_no_swept_surface_collision_model` (not a separate interblade status
field). Clearance:
`prepare_surface_clearance` → explicit **Katlanma boyunca yüzey açıklığını
denetle** → BVH + triangle distance + optional hardware
(`application/surface_clearance.py`, `geometry/triangle_distance.py`,
`geometry/hardware.py`). Unknown intervals stay unknown. Tests:
`tests/application/test_geometry_search.py`, `test_surface_clearance_service.py`,
`tests/geometry/`, `tests/ui/test_geometry_search_ui.py`,
`test_surface_clearance_ui.py`, `test_geom04_hardware_ui.py`.

### 6.5 Mechanism transient

Unbound page **Mekanizma Geçişi**: `_render_mechanism_transient` →
`prepare_mechanism_transient` / `run_mechanism_transient`. Bound path on
geometry page: JSON mass/drive → `prepare_bound_mechanism_transient` →
`dynamics/mechanism_transient.py` dense output until `_first_contact`. No
BEM/motor feedback. Tests: `tests/dynamics/test_mechanism_transient*.py`,
`tests/ui/test_mechanism_transient_ui.py`, `test_bound_mechanism_ui.py`.

### 6.6 Allow-listed PR-06D analysis

**Analiz Çalıştırma** uses only `pr06d_opening_sensitivity_v1`
(`application/analysis_run.py`): 254 mm UIUC fixture + archived
`reports/pr06d_opening_sensitivity.json`. Explicit button; session-only;
compares SHA to archive. Does **not** solve the 250 mm draft. Tests:
`tests/application/test_analysis_run.py`, UI analysis tests in
`test_streamlit_dashboard.py`.

### 6.7 Evidence import (not promotion)

**CFD / FEA / Deney** → `inspect_evidence_upload` with three canonical
identities (`apcsf-10x4.7-published-cfd-v1`,
`pr09-fea-contract-software-fixture-v1`,
`pr10-synthetic-test-stand-v1`). Session inspection only. Tests:
`tests/application/test_evidence_import.py`.

### 6.8 Polar real-backend (CI, not ordinary pytest)

Path-filtered / `workflow_dispatch` workflow builds pinned XFOIL 6.99, installs
NeuralFoil 0.3.3, captures bundles, regresses promoted golden
(`tests/fixtures/polar_real_qualification/`). Ordinary `tests.yml` uses doubles.

---

## 7. Authentication and authorization model

**None.** No users, sessions, roles, API keys, or RLS. Trust model is: whoever
can run Python/Streamlit on the checkout is a trusted operator
(`docs/development/commands.md`). Path containment applies to **dashboard
manifest evidence paths**, not to every CLI file API.

Do not treat `streamlit run` as a hardened multi-tenant service
(`.streamlit/config.toml` is theme/headless/upload size only).

---

## 8. Development commands

Authority: `pyproject.toml`, `.github/workflows/tests.yml`,
`docs/development/commands.md`. No Makefile, tox, npm, Poetry, uv, lockfile,
ruff, mypy, or pytest.ini.

| Operation | Canonical command | Notes |
| --- | --- | --- |
| Install | `python -m venv venv` then `./venv/bin/python -m pip install -e ".[dev,plot,ui]"` | extras: `dev`=pytest, `plot`=matplotlib, `ui`=streamlit+plotly, `neuralfoil` optional |
| Tests (CI-equivalent) | `./venv/bin/python -m pytest tests/ -q` | CI runs `pytest tests/ -q` after the same extras |
| Workspace | `./venv/bin/python -m streamlit run apps/pyfoldable_dashboard.py` | |
| Syntax | `./venv/bin/python -m compileall -q pyfoldable pythrust apps examples tests` | |
| Whitespace | `git diff --check` | |
| Wheel (packaging only) | `./venv/bin/python -m pip wheel --no-deps --wheel-dir outputs/wheels .` | not ordinary CI |
| Lint / format / typecheck | **not configured** | do not report as passed |
| E2E browser driver | **not configured** | Streamlit AppTest in `tests/ui/` |
| DB migrate/reset / codegen | **not applicable** | |
| Production deploy | **not configured** | |

**Command-style difference (not two different test suites):** README/`tests.yml`
say `pytest tests/ -q`; AGENTS/commands.md prefer the venv interpreter. Same
suite if the interpreter matches.

This cloud agent image had `venv/` with `[dev,plot]` already, **without**
`streamlit`/`plotly`, on **Python 3.12.3**, while CI matrices **3.10 and 3.11**.

---

## 9. CI/CD model

| Workflow | Trigger | What it does | Deploy? |
| --- | --- | --- | --- |
| `.github/workflows/tests.yml` | push `main` / `cursor/**`; PR to `main` | pip `.[dev,plot,ui]`; `pytest tests/ -q` on 3.10 and 3.11 | no |
| `polar-real-qualification.yml` | `workflow_dispatch` or PR when polar/XFOIL paths change | build pinned XFOIL; NeuralFoil==0.3.3; capture + golden regression; upload artifacts | no |
| `polar-real-reproducibility.yml` | manual two run IDs | download artifacts with `github.token`; compare bundles | no |

HEAD `d7afc39` Tests workflow run
[35213018209](https://github.com/Poyqraz/PyFoldable/actions/runs/35213018209)
succeeded on both Python jobs.

No required GitHub environment protection is defined in-repo. No migration
job. No release/publish workflow. Secrets: only GitHub-provided
`${{ github.token }}` for artifact download; XFOIL pins are public env names
in the workflow file (URL + SHA256 of the MIT tarball).

**Local vs CI gap:** local may be 3.12; CI is 3.10/3.11. Ordinary pytest does
not build XFOIL. Legacy tests skip without generated CSVs (9 skips). Wheel
install is not a tested workspace.

---

## 10. Test strategy

- **Unit/contract:** `tests/core/`, `tests/geometry/`, `tests/providers/`,
  `tests/application/` (strict JSON, hashes, fail-closed errors).
- **Integration:** BEM/rotor fixtures, dashboard snapshot vs reports, analysis
  run vs archived PR-06D JSON.
- **UI:** Streamlit `AppTest` in `tests/ui/` (10 files). Not Playwright.
- **Security-ish:** license/APC fixture class (`tests/test_license_policy.py`);
  upload budgets; path containment tests; XFOIL fake-exec tests.
- **Real-backend:** dedicated workflow + `tests/core/test_polar_real_*.py`
  against promoted fixtures.
- **No** SQL migration tests (no DB).

**Collected:** 1473 tests. **This audit run (Python 3.12.3):** 1464 passed, 9
skipped, 37 subtests passed in 149.63 s — same counts as GEOM-04 exact-head CI
on 3.11 recorded in `docs/agent/current-state.md`.

**Skip reasons (expected without `outputs/` pipeline):** motor-coupled CSV
missing (`tests/dynamics/test_report_generation.py`); foldable visualization
CSVs missing (`tests/test_visualization.py`, `test_concept_visualization.py`).
Other “Reference propeller not available” skips did **not** fire in this run.

**Coverage gap:** `tests/ui/test_streamlit_dashboard.py` `PAGES` omits
`Mekanizma Geçişi` from the generic navigation parametrize, while
`apps/pyfoldable_dashboard.py` includes it. Dedicated tests exist
(`test_mechanism_transient_ui.py`). Placeholder pages Motor–Pervane /
Doğrulama ve Kanıtlar / Raporlar have no product behavior beyond
`_render_planned_page`.

**Critical flows without a full product UI:** PY-06 comparison services
(`application/measurement_comparison.py`, `core/motor_rotor_correlation.py`,
`core/mechanism_observation.py`) are tested at Python layer, not as dashboard
pages (PY-06F planned).

---

## 11. Security-sensitive boundaries

1. **Dashboard path containment** — `application/dashboard.py::_inside_repo`
   (`resolve` + `relative_to(repo_root)`). Not a universal sandbox.
2. **Uploads** — polar 2 MiB; evidence 5 MiB; stations 128 KiB; hardware 256
   KiB; Streamlit `maxUploadSize = 5`. Declarative JSON/TOML only; nested-node
   budgets; duplicate-key rejection. No uploaded solver argv.
3. **XFOIL** — `subprocess.run([executable], input=script, cwd=tempdir,
   timeout=...)`; executable from trusted config/`PATH`
   (`providers/xfoil.py`).
4. **Polar cache locks** — regular-file check, `0o600`, advisory locks,
   owner metadata (`core/polar_cache_lock.py`).
5. **Qualification flags** — uploads and search reports reject
   `physical_qualification is not False` (multiple application modules).
6. **Third-party rights** — `data/propellers/apc_202602/` is first-party
   synthetic; APC PE0 is user-local only (`core/apc_pe0.py`,
   `THIRD_PARTY_NOTICES.md`).
7. **No** payment, webhook, or credential store. Do not print
   `github.token`.

Architectural risk: exposing Streamlit on a network without additional
controls equals full operator access to local solvers and files the process
can read.

---

## 12. High-risk modules

- `apps/pyfoldable_dashboard.py` (~1974 lines, many session keys)
- `pyfoldable/application/design_analysis.py` (private `_load*` reused by
  search/clearance; dashboard has an inline import of `_load_geometry`)
- `pyfoldable/application/geometry_search.py` vs `surface_clearance.py`
  (unknown constraints vs shipped clearance)
- `pyfoldable/geometry/triangle_distance.py` and mesh partitioning
- `pyfoldable/providers/xfoil.py` and cache lock files
- `pyfoldable/application/evidence_import.py` (identity allow-list)
- Dual model stacks: `pyfoldable/models.py` vs `core/models.py`; legacy vs
  PY-05 angle conventions
- `pyfoldable/application/analysis_run.py` (hard-coded checkout fixture paths)

---

## 13. Technical debt

- GEOM-01 diagnostic string still `unknown_no_swept_surface_collision_model`
  after GEOM-04 shipped (behavioral; do not silently mark passed).
- Placeholder UI pages despite PY-06/PR-07 Python APIs.
- Broad dependency ranges, no lockfile.
- Dashboard/private-helper coupling.
- Legacy tests skip without generated CSVs; green CI ≠ those integrations.
- Source hashes in reports change when implementation files change; restart
  long-lived interpreters (`design_analysis._implementation_identity`).
- Historical docs still say `pythrust/foldable/` (see drift).
- Open draft PR #3 (`cursor/foldable-nonlinear-closing-c1e3`) is unrelated
  and must stay outside this workstream (`AGENTS.md`).

---

## 14. Documentation drift

| Document | Claim | Repository reality | Evidence | Action |
| --- | --- | --- | --- | --- |
| `docs/agent/current-state.md` | Code baseline `ca81d2d` (2026-09-17) | Application code still that tree; HEAD is docs-only `d7afc39` | `git diff --stat ca81d2d..HEAD` | Keep as dated snapshot; this audit records HEAD |
| `tests/ui/test_streamlit_dashboard.py` | `PAGES` list for safe render | Missing `Mekanizma Geçişi` present in `apps/pyfoldable_dashboard.py` | both `PAGES` tuples | Optional test-list fix in a UI slice; not done here |
| `docs/foldable_conventions.md` | Conventions live under `pythrust/foldable/` | Code is `pyfoldable/dynamics/`, `pyfoldable/models.py`; `pythrust/` has only propellers/propulsion | glob `split_thrust.py` | Mark historical or retarget paths |
| `docs/superpowers/specs/v2_thrust_split_audit.md` | Scope `pythrust/foldable/dynamics/split_thrust.py` | File is `pyfoldable/dynamics/split_thrust.py` | glob | Treat as historical spec; do not follow path |
| `apps/pyfoldable_dashboard.py::_render_planned_page` | “UI-00/01 güvenli kabuk · Sonraki artımlarda test-first” | Those three pages are still placeholders; rest of UI is far past UI-01 | `main()` routing | Leave until those pages are implemented |
| `docs/development_roadmap.md` | “Complete in this change” on PR-05D | Self-labeled PR-04/05 history; later roadmap is `validation_and_development_roadmap.md` | header warning | Keep as history |
| `docs/python_research_execution_plan.md` | “after PY-05, the next ordered software slice is PY-06” | PY-06A–D1 and GEOM-01–04 later marked implemented in the same file | ordered-slices table | Prefer current-state / validation roadmap for “next” |
| `docs/py04_deterministic_design_search.md` | Local **1063 passed, 9 skipped** | Current suite 1464 passed, 9 skipped | pytest this audit; current-state | Leave as dated delivery record |
| README vs `docs/development/commands.md` | `pytest tests/ -q` vs `./venv/bin/python -m pytest tests/ -q` | Same suite; different interpreter discipline | `README.md`, `tests.yml` | Prefer the venv interpreter for agent work |
| `docs/agent/current-state.md` / this audit | GEOM-01 still reports unknown surface/interblade constraints | Constraint values stay `None`; details include `surface_path_clearance_status`: `unknown_no_swept_surface_collision_model` | `pyfoldable/application/geometry_search.py` | Keep wording; do not turn unknown into passed |

Correct and still true (spot-checked): no DB/auth; GEOM-04 does not select
GEOM-01 candidates; APC dir is synthetic; PR-06C blocked in dashboard.toml;
explicit UI buttons; `_inside_repo`; XFOIL argv subprocess.

---

## 15. AGENTS.md verification

| Statement | Class | Evidence |
| --- | --- | --- |
| Python research library + Streamlit workspace; software ≠ physical qualification | VERIFIED | `README.md`, `dashboard.toml`, `physical_qualification` greps |
| Progressive read: current-state → architecture → commands | VERIFIED | files exist and match |
| Evidence precedence code→tests→… | VERIFIED as policy | followed in this audit |
| Package map (`core/`, `application/`, `geometry/`, `dynamics/`, `visualization/`, `pythrust/`, `apps/`) | VERIFIED | directory listing |
| No DB, REST, login, role model; UI calls Python synchronously | VERIFIED | no Django/FastAPI/SQLAlchemy; Streamlit `main()` |
| Legacy `pyfoldable.models` ≠ `core.models` | VERIFIED | both modules |
| Install/test/streamlit venv commands; Python ≥3.10; CI 3.10/3.11 | VERIFIED | `pyproject.toml`, `tests.yml` |
| No lint/format/typecheck gate | VERIFIED | no ruff/mypy config |
| Do not assume untracked Cursor update script | VERIFIED | no `.cursor/` in repo |
| Units SI after parser; do not mix legacy and PY-05 frames | VERIFIED as invariant | `core/units.py`, `dynamics/mechanism_transient.py`, docs/ADR-004 |
| Hashes ≠ authenticity | VERIFIED | polar_upload/evidence_import wording + ADR-001 |
| Explicit UI actions; invalidate on change; drafts do not overwrite canonical | VERIFIED | buttons listed in dashboard; design_draft docstring |
| GEOM-04 does not auto-qualify GEOM-01 | VERIFIED | `geometry_search.py` None constraints |
| Upload / path / XFOIL / cache trust boundaries | VERIFIED | cited modules |
| `data/propellers/apc_202602/` first-party synthetic | VERIFIED | that README + license test |
| Preserve PR #3 | VERIFIED still open draft | `gh pr view 3` |
| Behavioral TDD; docs-only must not invent behavior tests | VERIFIED as process | CONTRIBUTING + commands.md |
| CLA sentence required | VERIFIED | `CONTRIBUTING.md`, `.github/pull_request_template.md` |

No INCORRECT AGENTS claims found at this HEAD. Dating of “current-state”
inside AGENTS is by link; that linked file is a **dated snapshot**
(PARTIALLY VERIFIED / expected).

---

## 16. Cursor Rules assessment

Tracked `.cursor/rules/` / skills / `environment.json`: **absent** (confirmed
`Glob` on `.cursor`). AGENTS.md is the only always-read project contract
(`docs/agent/handoff-protocol.md`).

Do **not** paste architecture overview into always-on rules.

Host-injected plugin rules (not in this repo) include TypeScript exhaustive
switch (irrelevant) and “no inline imports”. Repo code **does** use lazy
inline imports in `core/polar_config.py::_default_provider_factories` to avoid
importing optional XFOIL/NeuralFoil at config-parse time, and the dashboard
imports `design_analysis._load_geometry` inside `_render_geometry_search`.
Those are existing patterns; a repo rule forbidding them would be
**too broad / conflicting**. Prefer documenting lazy-provider exception in
architecture, not a global plugin copy.

---

## 17. Cursor Skills recommendations

Repeatable and repo-specific enough to consider **later** (not created here):

1. **`pr-readiness`** — exact-head CI, independent review, CLA sentence,
   merged-tree = tested-tree. Only if multiple agents keep missing it.
2. **`geom-unknown-scope`** — when changing search/clearance: preserve
   unknown, budgets, `full_propeller_clearance is None`, no GEOM-01 promotion.

**Not recommended now:** generic repo-onboarding skill (this audit +
`handoff-protocol.md`); test-impact skill (already in `commands.md`);
database-migration skill (no DB).

---

## 18. Current baseline test/build health

Failures below existed **before any documentation edit** on this branch.
Application code was not changed.

| Command | Result | Failures | Cause |
| --- | --- | --- | --- |
| `/workspace/venv/bin/python -m pip install -e ".[dev,plot,ui]"` | success | — | venv lacked ui extra initially |
| `pip check` | “No broken requirements found.” | — | |
| `compileall -q pyfoldable pythrust apps examples tests` | exit 0 | — | |
| `pytest tests/ -q -rs` | **1464 passed, 9 skipped, 37 subtests passed**, 149.63 s | none failing | 9 skips: missing generated CSVs |
| Lint/typecheck | not run | N/A | no repo gate |
| Polar real-backend workflow | not run | N/A | needs XFOIL build + NeuralFoil pin; path-filtered |
| GitHub Tests on `d7afc39` | success 3.10/3.11 | — | run 35213018209 |

Unstaged noise: `reports/foldable_v2_engineering_design/report_key_results.csv`
shows as modified due to CRLF vs `*.csv text eol=lf` in `.gitattributes`;
semantic content unchanged. **Do not commit.**

---

## 19. Unresolved questions

- Engineers’ CAD, material cards, ANSYS packages, and calibrated raw
  measurements (rights and quality) are still external.
- Representative spanwise polar / PR-06C physical gate remains blocked.
- Whether public hosting is desired; no in-repo answer.
- Cloud Agent environment is still not a tracked `.cursor/environment.json`;
  this run observed Python 3.12.3 + partial extras. Future agents must install
  `.[ui]` before AppTest.
- PR #3 draft intent vs main (nonlinear closing) is out of scope here.
- Whether to retarget historical `pythrust/foldable/` docs in a later docs
  slice (not done here).

---

## 20. Recommended next engineering priorities

Not authorized by this document; listed so agents do not restart finished work.

1. **Do not reimplement GEOM-04.** Shipped in PR #62/#63.
2. Next **bounded behavioral** slice proposed by current-state: connect
   **candidate-specific** scoped clearance into GEOM-01 search with RED tests,
   budgets, and unknown retained. Do not reuse one active-design clearance
   report for other geometry.
3. PY-06D2 / PY-06F / Motor–Pervane UI only when measured data or an explicit
   product decision exists.
4. Keep PR #3 and report CSV line-ending noise out of unrelated PRs.
5. Docs-only follow-ups: historical path retarget (`foldable_conventions.md`);
   optional AppTest `PAGES` completeness.

---

## Change protocol (for future Cursor tasks)

Before coding: record base commit; read AGENTS + current-state + relevant ADR
and feature contract; list tests from `docs/development/commands.md`; state
security/upload/hash impact; define rollback (revert those commits; preserve
unrelated work and PR #3).

During: narrow slice; no architecture tourism; no auth bypass (N/A) or
relaxed `physical_qualification`; no weakened tests; no secrets.

Before completion: targeted pytest; `compileall`; `git diff --check`;
CI-equivalent `pytest tests/ -q` when behavior changed; exact-head CI;
independent review; CLA sentence; report skips and evidence limits.

---

## Handoff template

Use `docs/agent/handoff-protocol.md`. Store checkpoints under
`docs/agent/handoffs/<task>.md` on the task branch when pausing.
