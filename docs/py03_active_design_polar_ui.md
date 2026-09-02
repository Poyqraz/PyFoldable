# PY-03 — uploaded polars and active-draft BEM

## Plan and scope

Extend merged PY-02 (`37e2054`, PR #50), not the fixed UI-04 benchmark.
Sequence: failing importer/service tests → strict upload contract → failing UI
action/invalidation tests → UI wiring → independent automated review → complete
regression/runtime checks → GitHub review/CI last → merge/tree verification.
This standing development workflow is also recorded in `AGENTS.md`.

Upload/run lives on **Tasarım Geometrisi**, below preparation. It uses the exact
current downloadable draft, without a second cross-page draft cache. **Analiz
Çalıştırma** still runs only the separate 254 mm benchmark. PR #3, canonical
designs, benchmarks and archived qualification gates are unchanged.

## Upload contract v1

One UTF-8 JSON object, with exactly these four mandatory root fields:

```json
{
  "schema_version": 1,
  "artifact_class": "active_design_polar_bundle",
  "physical_qualification": false,
  "tables": []
}
```

This empty array describes structure; it is **not runnable**. Each table has
exactly the `PolarTable` fields: `airfoil_id`, `scenario_id`, `reynolds`, `mach`,
`alpha_rad`, `cl`, `cd`, `cm`, `source`, `metadata`. Angles are radians; Reynolds,
Mach and coefficients are dimensionless. No automatic unit inference/conversion.
Reject duplicate/unknown fields, invalid Unicode, nonfinite numbers, numeric
strings, booleans as numbers, decreasing/duplicate angles, unequal coefficient
arrays and negative drag. Source text is displayed literally, not as Markdown.

All tables use one profile/scenario and unique Re/Mach cells; every Re/Mach
combination is required. Every table's lowercase 64-character
`metadata.airfoil_coordinate_sha256` must match the active draft's actual inline
coordinates. Alpha ranges may differ; solver queries remain strictly bounded.
No data is invented for missing cells or coefficients.

Nested provider metadata is preserved. Supplied `complete` must be literal true;
supplied `requested_point_count`/`usable_point_count` must equal table length.
These are consistency checks, not independently verified convergence. Any nested
`physical_qualification` must be literal false. Other provenance declarations
never establish qualified evidence or source authenticity.

Limits: 2 MiB raw bytes, 64 tables, 2–721 points/table, 16,384 points total;
JSON depth 16, 100,000 value nodes, strings 4096 characters, keys 256 characters.
Size is checked before UI materialization and again in the service. No archive
extraction, external URL fetching, subprocess or provider execution.

Export **already obtained** tables from the existing Python pipeline:

```python
import json
from dataclasses import asdict
from pyfoldable.application.polar_upload import inspect_polar_bundle

# family is an existing PolarFamily, not a substituted benchmark/proxy.
payload = json.dumps({
    "schema_version": 1,
    "artifact_class": "active_design_polar_bundle",
    "physical_qualification": False,
    "tables": [asdict(table) for table in family.tables],
}, allow_nan=False).encode("utf-8")
inspect_polar_bundle(payload)  # Validate before saving/uploading these bytes.
```

Never attach a new coordinate hash to old polars to make them pass. Obtain or
regenerate polars for the exact coordinate realization. This slice does not run
XFOIL/NeuralFoil automatically or supply fake demonstration performance data.

## Execution, identity and limitations

`prepare_polar_run(draft, payload, annulus_count=40)` checks identity and the
fully-open/positive-RPM domain without BEM. `run_polar_run(request)` revalidates
the immutable request and invokes existing `run_design_analysis`. UI budget is
4–80 annuli, default 40; existing solver defaults are fixed (128 bracket samples,
100 iterations), `station_span`, `bounds="error"`. No wall-clock timeout is
promised. No solver replacement or new physics model is introduced.

The JSON report retains exact uploaded text/raw SHA, normalized SHA, full UI
request/hash preimage, draft TOML, runtime/source identities, full polar tables,
settings, annulus results and actual query envelope. Filenames are excluded from
identity; changes to bytes/whitespace invalidate it. Hashes bind content but do
not authenticate sources. Output stays screening-only, physical false. Nominal
station ranges and rectangular grids do not prove complete BEM query coverage;
out-of-range queries stop without clamping, extrapolation or partial totals.

Only the explicit button solves. Rerenders do not solve again. Draft, upload or
annulus changes remove old output/downloads; so do invalid geometry, missing or
invalid upload, preparation failure and failed reruns. Results are session-only,
without config/repository/report writes. UI reports shaft torque/power, not
hinge torque or battery power.

The 140 mm folding conflict, external-data gates and unknown material/structural
constraints remain. No 85% thrust retention or matched-condition denominator is
claimed. Printing orientation/manufacturing DoE remain outside this slice.

## Acceptance and next slice

Test-first checks cover schema/types/budgets, profile/hash mismatch, provider
declarations, exact provenance, immutable request revalidation, real-kernel runs
with synthetic **test-only** coefficients, strict bounds, explicit UI actions,
input changes and no stale success after failure. Independent review found and
helped close escaped-surrogate rendering and active-Markdown source display bugs.

Next: **PY-04 / PR-11A**, deterministic sweep/optimizer infrastructure using the
existing analysis callback, not a physically qualified optimum.

Local verification on 2026-09-02: **990 passed, 9 skipped**, including 86 new
service/UI tests. `compileall` passed for the package, compatibility package,
examples, tests and app. A real Streamlit server returned HTTP 200 `ok` on its
health endpoint and was stopped after the check. Independent re-review passed
all 86 new tests with no remaining blocker. GitHub CI/review remains the merge
authority; skipped tests and synthetic fixtures are not physical evidence.
