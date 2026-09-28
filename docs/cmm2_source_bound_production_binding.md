# CMM-2 source-bound production binding

Status: implemented, independently reviewed, and merged in PR #78.
ADR-008 is accepted for this screening software integration.
Final reviewed head `653526bca79160a2ec41e2e2ebea802dd8b39d1c`.
Merge commit `6f72b28273b38334851df570b1c4cccbbc6b5140`.
This is a screening service. `physical_qualification` stays false.

The service lives in `pyfoldable/application/cmm2_coupled_transient_service.py`.
It does not modify CMM-1, the accepted planar-map mathematics, or the pure
CMM-2 dynamics callback API.

## Identifiers

| Name | Value |
| --- | --- |
| Service id | `pyfoldable.application.cmm2_coupled_transient_service` |
| Service implementation id | `cmm2_source_bound_screening_service_v1` |
| Dynamics implementation id | `cmm2_planar_projected_rate_independent_coupling_v1` |
| Aero evaluator id | `cmm2_foldable_bem_planar_map_v1` |
| Motor law | existing `Pr07MotorEvaluator` (`cmm1_pr07_motor_algebra_v1`) |
| Schema version | `1` |

The service implementation id and the dynamics implementation id are different.
The report records both.

## Call

Each aerodynamic evaluation does this and nothing else for the load:

```text
bem_result = solve_foldable_bem_rotor(...)
mapped = map_foldable_bem_aero_loads(bem_result, hinge_rate_rad_s=theta_dot)
```

`mapped` is computed from that returned object. The evaluator then sets:

```text
whole_rotor_shaft_generalized_load_nm =
    mapped.whole_rotor_aerodynamic_shaft_generalized_load_nm
one_tip_hinge_generalized_load_nm =
    mapped.one_tip_hinge_generalized_torque_nm
thrust_n = mapped.source_whole_rotor_projected_thrust_n
```

`result.rotor_result.torque_nm` is stored in the provenance ledger only as
`raw_bem_resisting_torque_nm_not_used_as_cmm2_generalized_load`. It is not
the shaft generalized load. The shaft load is not multiplied by `N`.
`synchronous_n_times_one_tip_hinge_generalized_torque_nm` is stored in the
ledger and is not written into the one-tip field. The dynamics multiply the
one-tip field by `N` once.

A BEM or map failure raises `Cmm2TransientFailure` and keeps the original
exception as the cause. The service does not substitute zero hinge load and
does not fall back to the raw BEM torque. `bounds` must be `"error"`.
`"clamp"` is rejected before a BEM call. The selected loading branch is the
branch passed into `solve_foldable_bem_rotor`.

Successful solves, successful maps, ledger rows, and
`result.aero_evaluations` are the same count. A sample source id resolves to
one ledger row, and that row's angle, hinge rate, and shaft speed match the
sample.

## Source id

```text
cmm2-planar-map:{evaluation_index}:{mapped_load_sha256}
```

`mapped_load_sha256` is the SHA-256 of the canonical UTF-8 JSON of
`mapped.as_mapping()`. The same mapped document produces the same digest.
The evaluation index keeps two successful evaluations distinct when the
mapped document repeats. The operating-condition id does not include that
index. The fold-state id does, and it is part of the separate BEM result
digest.

## Seal and report

`prepare_cmm2_coupled_transient` writes canonical UTF-8 JSON and
`input_sha256 = sha256(context_json)`. The payload includes the draft, mass
distribution, base inertia, motor, battery, system, throttle, environment,
polars, BEM settings, bounds, controls, spring, rest angle, damping, dry
friction, mechanical source, actuation, and the initial state. It also
includes the planar load-contract identity and version. Changing a sealed
input changes the digest. Mutated metadata fails closed. Nonfinite metadata
fails closed.

`run_cmm2_coupled_transient` rejects a mismatched `expected_input_sha256`.
The report contains the sealed request, both hashes, implementation-file
hashes, the provenance ledger, and the serialized result.
`report_sha256` is the SHA-256 of that report JSON. Two runs of the same
sealed binding produce the same report bytes.

`implementation_files_sha256` records an explicit reviewed manifest of
first-party source files whose executable model, binding, calculation,
acceptance, or numerical logic materially defines the source-bound screening
service and result. It is provenance identity. It is not a complete automatic
import graph, a dependency lock, authentication, proof of correctness, or
physical validation. Paths are repository-relative and are not normalized
before rejection. The draft loader, SI unit normalization, planar geometry
audit, and inline airfoil acceptance check are on that manifest because they
can change the bound geometry or reject the binding.

A hash identifies content. It does not authenticate a source, prove
numerical correctness, or establish physical validation.

## What this slice does not do

Independent CMM-2 numerical verification is not started. There is no
dashboard. PR-06C stays unresolved. No GEOM gate is promoted. There is no
calibration and no experimental validation. CMM-1 still omits aerodynamic
hinge torque. The accepted load map is unchanged.

Dynamics contract: [CMM-2 PR-A](cmm2_coupled_transient_contract.md).
Load map: [planar aero-load prerequisite](cmm2_planar_aero_load_prerequisite.md).
Decision: ADR-008, accepted for this screening software integration after
independent review and merge in PR #78.
