# GEOM-02 — explicit source-bound blade stations

GEOM-02A adds `parse_station_bundle`, `audit_station_bundle` and
`export_station_bundle` in `pyfoldable.application.blade_stations`, plus the
optional `station_bundle` input to `build_design_draft`. The canonical design
remains read-only. GEOM-02B connects the contract to the active geometry editor.

GEOM-02A was merged in [PR #59](https://github.com/Poyqraz/PyFoldable/pull/59)
after successful Python 3.10/3.11 CI and independent automated review. Its merged
tree matched the reviewed tree `88e1c0aa0628be2becb0c9c7ccf2632ab2e9441c`.

## Input contract

UTF-8 JSON, at most 128 KiB, with exactly these fields:

```json
{
  "schema_version": 1,
  "units": {"length": "mm", "angle": "deg"},
  "diameter": 250,
  "hub_radius": 18,
  "airfoil_id": "NACA2412",
  "airfoil_coordinate_sha256": "<actual SHA-256 of the selected coordinate definition>",
  "provenance": {
    "kind": "declared_design",
    "reference": "User-supplied geometry; not a measurement",
    "locator": "Explicit station table",
    "revision": "1"
  },
  "stations": [
    {"radius": 18, "chord": 3, "twist": 20},
    {"radius": 70, "chord": 2, "twist": 10},
    {"radius": 125, "chord": 1, "twist": 5}
  ]
}
```

The numbers above are synthetic contract examples, not recommended geometry or
literature measurements. Replace the descriptive hash placeholder with the exact
selected profile hash. Supported lengths: m, mm, cm, in; angles: rad, deg.
There must be 2–64 strictly increasing positive radial positions, positive chord,
and finite twist. Unknown fields, duplicate keys, booleans/numeric strings,
nonfinite values, invalid UTF-8 and unsupported units fail closed. One shared
explicit coordinate-bound profile, at most 601 coordinates, is supported.

Provenance kind is declared_design, literature_geometry, project_measurement or
derived_geometry. It describes the submitter's source claim, not authentication
or qualification. Derived geometry also requires parent_sha256. Each bundle has
one shared provenance record; mixed-source tables require externally documented
consolidation into a derived bundle. Raw bytes and canonical SI JSON have separate
hashes; exported JSON is canonical SI. Exact raw JSON and both hashes are retained
in draft metadata. A digest alone does not embed or authenticate a parent file;
retain source files when distributing derived artifacts.

## Binding and evidence limits

The active diameter, hub and selected profile must match the bundle. Physical
positions and chords are never resized on application. Legacy chord and twist
scales must both equal one in explicit mode. The legacy source-station path is
unchanged; re-scaling a saved imported draft removes its obsolete station
metadata and retains its source-design hash as the parent link.

Coverage uses an eight-ULP arithmetic tolerance at the root and tip. Valid partial
coverage remains visible as incomplete, without extrapolated sections. Applying
a draft requires the hinge strictly inside the defined station span. The audit
reports root/tip gaps and hinge coverage separately. Surface-path and interblade
clearance remain unknown, including with complete stations. No mass, inertia,
material properties, aerodynamic validity, CAD solid or physical qualification
is inferred. The GEOM-01 full-180-degree 143 mm necessary centreline bound is
unchanged for the 250 mm diameter, 18 mm hub and supported topology.

## Development evidence

TDD first observed the missing station module, then passed 46 contract tests.
Tests cover malformed input, equivalent units, source forgery, actual root
overlap/gaps, partial coverage, profile binding, no double scaling, raw-byte
retention, serialization round trips and removal of stale inherited metadata.
The complete application test directory passed (412 tests, 18 subtests).
Independent automated review found no blocking GEOM-02A issue. Exact-head CI and
final GitHub reviews remain the shipping gates.

## GEOM-02B workspace

In **Tasarım Geometrisi**, choose **Kanat istasyonu kaynağı → Açık istasyonlar**.
The initial table copies the current parametrically scaled geometry once. Edit
radial positions/chord in mm and twist in degrees, or upload a station JSON file.
Calculated r/R is read-only. Validation reports root/tip gaps and hinge coverage;
partial but valid datasets stay partial. Click **İstasyonları uygula** to activate
the table. Preview, active station table, TOML download, GEOM-01, BEM preparation
and mechanism binding all use the same round-tripped draft.

The chord/twist sliders are disabled in explicit mode and are not reapplied to
uploaded measurements. Changing diameter, hub or profile invalidates the binding.
**Tabloyu güncel ölçülere yeniden bağla** explicitly revises that binding while
preserving all station SI values; it does not move sections or extrapolate tips.
Reapply afterwards. Untouched cells preserve exact SI values during table edits.

Editing, changing/removing an upload, mode switches and failed application clear
the applied state and old geometry/BEM/search/bound-mechanism/transient results.
Restoring old inputs does not resurrect a previous result. Analysis remains an
explicit action. Changed mass/geometry bindings and polar coverage need their
own existing validation; no mass/inertia or aerodynamic coefficient is generated.

Use **İstasyon kaynak JSON indir** to retain the original source for the current
editor revision and **Etkin istasyon JSON indir** for the applied SI bundle.
Edits/rebinding are derived geometry with a parent hash. Retain each parent file
alongside distributed revisions; hashes are references, not embedded ancestry.

TDD additionally reproduced failed-apply downloads and display-unit drift, then
fixed both. Eight Streamlit AppTest scenarios cover explicit application,
upload replacement, edit/rebind provenance, mode switching, draft/preview
equivalence and failed application. The editor test renders the actual widget
and injects edited rows because AppTest does not reliably retain data-editor edit
events between runs. Three extra audit regressions prevent a physical 1e-12 m
root/tip gap or overlap from being called complete by a broad engineering
tolerance. Surface/interblade constraints and the 143 mm bound remain unchanged.
