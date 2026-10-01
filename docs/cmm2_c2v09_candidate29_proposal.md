# C2V09-29 prospective synthetic terminal declaration

Status: **PROPOSED / NOT FROZEN / NOT IMPLEMENTED**.

This is a proposed append-only continuation of the [numerical-feasibility
amendment](cmm2_numerical_feasibility_amendment.md), not an executable fixture.
Base/source is `4cf0d0ea017fa824ba8d4a063ceddd015dae09d6`. Main ships RK45/v1;
PR #84 contains an unmerged Radau/v2 attempt. PR #81 and PR #84 remain
Draft/BLOCKED. This document does not approve either implementation.

## 1. Before / after and immutable provenance

| Item | Preserved / proposed |
| --- | --- |
| Frozen selector | `prc_c2v09_ordered_candidates_v1`, original00…27 unchanged |
| Earlier proposed selector | v2 adds28; its complete manifest, hashes and mapper rejection remain in the parent document |
| New proposed selector | `prc_c2v09_ordered_candidates_v3_proposed`: 00…27,28,29; only append29 |
| Candidate28 | BEM succeeded; mapper rejected its 0.98-terminal coverage gap; not selected |
| Candidate29 | Inherits28, retains every existing station and numerical input, appends exactly one synthetic terminal station |
| Implementation | None; no executable fixture, test, production, workflow or ADR change |

Candidate28's manifest hash remains
`c2061c293190a5fec947230b89c98c553da22aab738b6146c54fd49955dfb547`;
its draft remains `94553fbeaf4f41a01ee998cb51f13bc6fc34ac2ceecdf8b6d482cd63ea03c3f0`
and main-v1 seal remains
`1c814e7a4b4b5229a56e91679a6920567676439efd471fbe5277de914e0aca54`.
The historical geometry source remains
`a3852e5d14f433528fa9ad63bae26dd076b5136eacf4a7860ef76971eec2afdc`.
None is relabelled as candidate29 evidence. The pinned original rejection and
C2V-07 certificate in the parent proposal remain the evidence for their own
heads; no new C2V-07 polynomial or trajectory was measured here.

Append this literal before `[[airfoils]]`, through the inherited unit parser:

```toml
[[blade.stations]]
r_over_R = 1.0
chord = "7.04 mm"
twist = "5.0 deg"
airfoil = "NACA0012"
```

This is **first-party synthetic constant continuation on [0.98,1.0]** of the
preceding station's literal chord/twist/airfoil. It is prospective verification
geometry, not recovered, measured or experimentally established blade data.
Parsed chord is `0x1.cd5f99c38b04bp-8` m and twist is
`0x1.657184ae74487p-4` rad, identical to the preceding parsed station.
Every inherited station, mass/inertia, motor, environment, controls, four-annulus
count and numeric polar coefficient is preserved. `radial_domain="station_span"`
is preserved. Extending the outer station span reconstructs all four quadrature
cells and midpoints; it does not preserve their old positions. `hub_to_tip`
would also change the inner domain and is broader than this proposal.

The complete source recipe and new draft metadata below explicitly separate
synthetic geometry identity from the inherited canonical source. New identity
fields are design id/description, source id/hash, synthetic owner/classification,
interval/law/status, false qualification/experimental flags, and inherited
candidate28/source hashes. No physical coefficient is changed. Hashes identify
content, not authenticity, acceptance or physical validity.

## 2. Source-expression proof and conditional four-dimensional certificate

Source authority: [foldable projection](../pyfoldable/core/foldable_rotor.py),
[radial cells/interpolation](../pyfoldable/core/bem_rotor.py),
[BEM queries](../pyfoldable/core/bem.py),
[spanwise interpolation](../pyfoldable/core/polar_spanwise.py), and
[native mapper normalization](../pyfoldable/core/foldable_aero_load.py), all at
base4cf above. Stored binary64 values are converted directly to Fraction.

Let R be parsed diameter/2, h the hinge and c the emitted projection factor.
The source computes `effective_radius = h + (R-h)*c`. At the appended station,
`nominal_radius = 1.0*R = R`; its projected `local_radius` uses exactly
`h+(nominal_radius-h)*c`. These identical operations/operands give the same
stored binary64 radius. `local_ratio=local_radius/effective_radius` is exactly
1.0. Reconstructing radius from `diameter=2.0*effective_radius` and division by
2.0 is exact for these finite normal ranges. The projected upper polar anchor
also uses the same effective-radius expression and normalizes to exactly1.
The first station/anchor stays at `RN(0.2*R)` divided by effective radius.
This proof uses source expressions, not an enlarged coverage tolerance.

Station-span cell width is `RN((tip-first)/4)`, endpoints are
`RN(first+i*width)`, midpoint is `RN(0.5*(a+b))`, span query is
`RN(midpoint/tip)`, and the annulus kernel recomputes `RN(ratio*tip)`.
The final outer endpoint must still be checked independently: native
FoldableBEM's guarded source-bound terminal normalization is unchanged. Record
its **original source radius and signed delta**, even when normalization occurs.
The generic mapper remains exact/fail-closed; no loads are fabricated in28's
old gap and no tolerance is enlarged. For29 that interval is declared geometry.

The following certificate is **a priori and conditional**, not trajectory
coverage. States are theta in[-0.5,0], shaft speed in[OMEGA_MIN,600], unchanged
forward speed4/environment, and positive-only BEM branch. It assumes actual
emitted projection c in[7/8,1], ordered projected stations and successful
interpolation weights in[0,1]. Nominal station chord/twist literals, inserted
hinge interpolation and all radial RN operations are enclosed outward by exact
rational arithmetic and adjacent binary64 endpoints. Every successful chord
lies inside[0.001,0.1] m and twist inside[-1.5,1.5] rad.

For actual emitted trigonometric values require nonnegative sin/cos(psi),
`s^2+c^2 <= 1+2^-40`; actual E/W hypot and sound sqrt results must differ
from their exact rational Euclidean/square-root enclosures by at most2^-40
in their respective SI units; emitted atan2 lies in[0,nextup(pi/2)]. These are
explicit conditional runtime checks, **not a universal libm accuracy theorem**.
With positive source branch and V=4, W is at least2−2^-40. The norm triangle,
U<=RN(600*0.11), E=hypot(4,U), bounded scalar/vector RN error and checked libm
outputs yield W<67 m/s. For scalar operations below128, error is below2^-46;
the conservative vector allowance is below2^-40. The executable exact-rational
construction in Appendix C records all endpoints and margins; displayed
rounded decimals are not its certificate.

Mach support is[0,0.2], Reynolds support[1,1e6], alpha support is
[-`0x1.921fb54442d19p+1`,+`0x1.921fb54442d19p+1`] rad. All four dimensions,
including spanwise anchor/cell coverage, must pass their actual emitted-query
checks. `bounds="error"` remains. Outside any conditional state/runtime/source
hypothesis, coverage is unproven and failure is retained; this is not unlimited
BEM query coverage or permission to clamp.

- `effective_tip`: exact outward endpoints `1925288840700887/18014398509481984`, `7926335344172073/72057594037927936`; hex `0x1.b5c28f5c28f5cp-4`, `0x1.c28f5c28f5c29p-4`.
- `projected_lower_anchor`: exact outward endpoints `7205759403792793/36028797018963968`, `7416454123201941/36028797018963968`; hex `0x1.9999999999999p-3`, `0x1.a5939c981a595p-3`.
- `projected_upper_anchor`: exact outward endpoints `1`, `1`; hex `0x1.0000000000000p+0`, `0x1.0000000000000p+0`.
- `chord`: exact outward endpoints `4058283696216101/576460752303423488`, `3550998234189089/144115188075855872`; hex `0x1.cd5f99c38b04ap-8`, `0x1.93b3a68b19a42p-6`.
- `twist`: exact outward endpoints `6288211335136391/72057594037927936`, `4873363784730703/9007199254740992`; hex `0x1.657184ae74487p-4`, `0x1.1504c6d40084fp-1`.
- `mach`: exact outward endpoints `6718030833896239/1152921504606846976`, `3470340589211141/18014398509481984`; hex `0x1.7de037171cb2fp-8`, `0x1.8a88344239c0ap-3`.
- `reynolds`: exact outward endpoints `4638833415061773/35184372088832`, `7488397774637227/17179869184`; hex `0x1.07afe91e0810dp+7`, `0x1.a9aa8794b48abp+18`.
- `alpha`: exact outward endpoints `-6914818596542093/2251799813685248`, `3/2`; hex `-0x1.890fdaa22168dp+1`, `0x1.8000000000000p+0`.

Four span-query intervals (all strictly inside the projected anchor span):

| Cell | Lower hex | Upper hex |
| --- | --- | --- |
| 0 | `0x1.2f904a7904a78p-2` | `0x1.3c2eb57213c31p-2` |
| 1 | `0x1.f51745d1745cfp-2` | `0x1.077c41df1077ep-1` |
| 2 | `0x1.5d4f2094f2093p-1` | `0x1.70e12905170e4p-1` |
| 3 | `0x1.c0129e4129e3fp-1` | `0x1.da46102b1da48p-1` |

Minimum exact lower/upper span margins are `3264241811255131/36028797018963968` and `82961045767351/1125899906842624`.

## 3. Declaration before measurement and fixed initial-only plan

The complete manifest/literal and pure recipe are committed and separately
reviewed at an exact declaration HEAD **before** the first29 motor/BEM/mapper
measurement. Parsing, seal construction and rational algebra make no source
calls. Declaration review checks inherited inputs, four-dimensional conditional
coverage, terminal-expression identity and measurement separation. No29 result
is used to adapt this geometry, table, controls, preflight or gates.

After that review only, build the real main-v1 request, evaluate the real PR-07
motor once at `(t,theta,v,omega)=(0,-0.2,0.01,400*pi/30)`, and evaluate fresh
real BEM/mapper repeatedly at that same state. Observe real unchanged call
arguments/results and all emitted queries; capture source hashes, Python,
NumPy/SciPy/libc/platform, implementation identity and scratch-script hash.
Record projected stations/anchors/interpolation, radial cells/field intervals,
query envelopes and original terminal-normalization provenance. Verify the
conditional source hypotheses against emitted arithmetic, retaining failures.

Complete every frozen initial preflight if mapping succeeds:

1. Independently spell binary64 mechanical assembly from declared mass/inertia,
   mechanics, state and fresh lower-layer loads. Exact Fraction solve/inverse
   and represented residual audit use frozen `prc_represented_forward_v1`,
   row backward errors, kappa/rho, factor-two theorem and zero branch. The
   production acceleration call is only the subject. Production mass/Schur
   assembly or private request builders are not the equation oracle.
2. Independently replace q_theta by0 and mapped Q_phi by the **same BEM's** raw
   positive torque. Compare exact represented acceleration gaps against the
   unchanged B_abs_correct. Compute the derivative of declared mechanical
   energy independently from the exact reference accelerations, not production
   `power_identity`; apply frozen P_scale_09/U_P09 and hinge-work predicate.
3. Record fold/shaft margins using unchanged initial scales. Enumerate actual
   mapped interval edges, hinge-containing radial cell endpoints and radial
   midpoint boundaries by source identity. Apply frozen radius uncertainty.
   Do not silently exempt an edge's own boundary to manufacture a positive
   margin. A literal zero margin or unresolved normative interpretation remains
   a preflight/contract blocker and requires later independent contract review.
4. For Q4 make two actual calls of one evaluator (index0 then1, real FoldableRotor
   state/schedule IDs change); additionally rebuild the same numeric schedule
   with exactly one permitted metadata addition to **each** table:
   `q4_probe="candidate29-q4-metadata-v1"`, leaving all existing metadata,
   sources, arrays, anchors, settings and physical inputs unchanged. Seal this
   distinct metadata binding separately. Prove the changed state/index and
   table metadata reach real BEM and that each returned real object is passed
   to the real mapper. Compare finite thrust, whole-rotor Q_phi and one-tip
   q_theta via eight-byte IEEE encodings including signed zero. Different report
   IDs alone are insufficient. A bit mismatch is a production defect/contract
   block, not a reason to replace a candidate.

The complete proposed Phase A/B selector is the parent document section4 with
order00…27,28,29: Phase A exact reconstruction/seal failure stops; Phase B
expected source/convergence rejection or failed predicate records its cause
and continues; unexpected/provenance failure stops; Q4 mismatch stops. Select
the first candidate passing **every** requirement. This authorized29 probe is
an isolated prospective-candidate check, not a new canonical full walk or
selection. No candidate is selected by this document. Original walk and28
failure stay visible. No production/reference trajectory, DOP853 integration,
trajectory acceptance metric or step placement search is authorized here.

Main-v1 seal is for initial-only feasibility and cannot be relabelled future
Radau/v2 evidence. A future v2 seal must bind the independently reviewed/frozen
technical head, implementation/runtime and actual source payload. Q1–Q4 gates,
DOP853 A/B levels, fixture order, controls, max e_j<=1 and state tolerances stay
unchanged. Q4 bit identity is an initial observation only; Q5 runtime,
partition and minimum-SciPy evidence remain pending. Local SciPy1.17.0 is not
CI1.15.3 or1.17.1 evidence.

## 4. Measurement status and acceptance prerequisites

Declaration-time status: **NOT MEASURED / NOT SELECTED**. Source calls0;
trajectory calls0. Results may be appended only after committed-declaration
review. Any failed requirement remains visible; no repeated measurement-driven
fixture adaptation. Initial success, if any, does not establish trajectory
verification or freeze readiness.

Before implementation/freeze: review this append-only manifest and timestamp
policy independently; resolve source/preflight/partition blockers; explicitly
approve/freeze amended contracts under separate authorization. Later implement
and verify v2 against the exact seal/runtime, run the complete ordered initial
walk, preserve all numerical gates and independent reference separation,
remeasure DOP853 stabilization at actual new production sample times, and
complete C2V07/09 plus all required evidence. No historical acceptance record
is rewritten. Independent CMM-2 numerical verification is NOT ESTABLISHED;
ADR-009 NOT CREATED / NOT ACCEPTED; physical_qualification=false; PR-06C
unresolved; GEOM promotion/calibration/experimental validation NONE.

## Appendix A. Complete candidate29 canonical manifest

Canonical digest rule is recursive float leaf to `{ "binary64": value.hex() }`,
then sorted compact ASCII JSON, UTF-8 without trailing newline. Preserve array
order, strings, integers, booleans and null. Draft digest instead hashes exact
UTF-8 TOML bytes; source recipe uses the canonical rule; existing v1 service
seal retains its existing context JSON rule. They are distinct identities.

- `candidate29_draft_sha256`: `b3d3fd8e58a2476937607e04ecd2651b91cfb4c95c44ea026a39eff57dc167d6`.
- `candidate29_manifest_sha256`: `0b37fb45c005d7a046dee6541d1a89e4a0a5cead7434621718c90d191843b7a4`.
- `declaration_recipe_sha256`: `053958f8d0cceb80e425efd6a4411c1e262f340c784042c1fc9944169746dc21`.
- `main_v1_preflight_seal_sha256`: `389d5565d179358b4530bc98038f3046291594615d1acb0d3873655f678595b9`.
- `synthetic_source_recipe_sha256`: `61048f3143ad1074e7e1e822b847cb7a93ba27315c9676d8b1dc43936439736e`.

```json
{
  "base": "4cf0d0ea017fa824ba8d4a063ceddd015dae09d6",
  "candidate_id": "C2V09-29",
  "draft_toml": "schema_version = 1\n\n[design]\nid = \"C2V09_29_SYNTHETIC_TERMINAL_DRAFT\"\ndescription = \"First-party synthetic constant terminal continuation of C2V09-28 for numerical verification only\"\n\n[blade]\ndiameter = \"220.0 mm\"\nhub_radius = \"16.0 mm\"\nblade_count = 3\n\n[[blade.stations]]\nr_over_R = 0.2\nchord = \"24.64 mm\"\ntwist = \"31.0 deg\"\nairfoil = \"NACA0012\"\n\n[[blade.stations]]\nr_over_R = 0.4\nchord = \"22.88 mm\"\ntwist = \"24.000000000000004 deg\"\nairfoil = \"NACA0012\"\n\n[[blade.stations]]\nr_over_R = 0.6\nchord = \"20.240000000000002 mm\"\ntwist = \"17.0 deg\"\nairfoil = \"NACA0012\"\n\n[[blade.stations]]\nr_over_R = 0.8\nchord = \"14.96 mm\"\ntwist = \"10.0 deg\"\nairfoil = \"NACA0012\"\n\n[[blade.stations]]\nr_over_R = 0.98\nchord = \"7.04 mm\"\ntwist = \"5.0 deg\"\nairfoil = \"NACA0012\"\n\n[[blade.stations]]\nr_over_R = 1.0\nchord = \"7.04 mm\"\ntwist = \"5.0 deg\"\nairfoil = \"NACA0012\"\n\n[[airfoils]]\nid = \"NACA2412\"\nsource = \"analytic_naca_4_digit\"\n\n[[airfoils]]\nid = \"NACA0012\"\nsource = \"analytic_naca_4_digit\"\n\n[[operating_conditions]]\nid = \"hover_7100_rpm\"\nangular_speed = \"3999.9999999999995 rpm\"\nforward_speed = \"4.0 m/s\"\nair_density = \"1.18 kg/m^3\"\ndynamic_viscosity = \"1.79e-05 Pa*s\"\ntemperature = \"293.15 K\"\npressure = \"100000.0 Pa\"\n\n[hinge]\nradius = \"85.0 mm\"\naxial_offset = \"0.0 mm\"\ntangential_offset = \"0.0 mm\"\naxis_azimuth = \"0.0 deg\"\naxis_elevation = \"90.0 deg\"\nstowed_angle = \"-180.0 deg\"\ndeployed_angle = \"0.0 deg\"\nstop_angle = \"0.0 deg\"\n\n[motor]\nid = \"REFERENCE_980KV\"\nkv = \"980.0 rpm/V\"\nresistance = \"0.06 ohm\"\nno_load_current = \"1.2 A\"\nmax_current = \"30.0 A\"\n\n[manufacturing]\nprocess = \"FFF\"\nmin_wall_thickness = \"1.2 mm\"\nmin_trailing_edge_thickness = \"0.8 mm\"\nbuild_orientation = \"to_be_verified_by_coupon_tests\"\n\n[metadata]\nartifact_class = \"unqualified_design_draft\"\nnote = \"Airfoil, chord, and twist values are initial schema examples, not validated design claims.\"\npreview_fold_angle = \"-59.999999999999993 deg\"\npreview_fold_angle_semantics = \"UI preview pose; not a hinge stop or a physical result\"\nproject = \"PyFoldable\"\nsource_design_id = \"c2v09-29-synthetic-constant-terminal-v1\"\nsource_design_sha256 = \"61048f3143ad1074e7e1e822b847cb7a93ba27315c9676d8b1dc43936439736e\"\nstowed_envelope_requirement = \"140 mm\"\nsynthetic_geometry_owner = \"PyFoldable\"\nsynthetic_geometry_classification = \"synthetic_test_fixture\"\nsynthetic_geometry_id = \"c2v09-29-synthetic-constant-terminal-v1\"\nsynthetic_geometry_interval = \"r_over_R=[0.98,1.0]\"\nsynthetic_geometry_law = \"constant preceding-station literal chord/twist/airfoil\"\nsynthetic_geometry_status = \"PROPOSED / NOT FROZEN / NOT IMPLEMENTED\"\nsynthetic_geometry_experimental_validation = false\nsynthetic_geometry_physical_qualification = false\ninherited_candidate28_manifest_sha256 = \"c2061c293190a5fec947230b89c98c553da22aab738b6146c54fd49955dfb547\"\ninherited_candidate28_draft_sha256 = \"94553fbeaf4f41a01ee998cb51f13bc6fc34ac2ceecdf8b6d482cd63ea03c3f0\"\ninherited_canonical_source_sha256 = \"a3852e5d14f433528fa9ad63bae26dd076b5136eacf4a7860ef76971eec2afdc\"\n",
  "effective_binding": {
    "actuation": {
      "source": "no actuation",
      "time_s": [
        0.0,
        0.004
      ],
      "torque_nm": [
        0.0,
        0.0
      ]
    },
    "aero_evaluator_id": "cmm2_foldable_bem_planar_map_v1",
    "aero_load_status": "signed_paired_generalized_loads",
    "base_rotating_inertia": {
      "component_inventory": [
        "motor rotor",
        "shaft",
        "hub",
        "fixed blade roots"
      ],
      "excludes_modeled_movable_tips": true,
      "inertia_kg_m2": 0.0001,
      "source": "fixture inertia"
    },
    "battery": {
      "discharge_efficiency": 0.98,
      "voltage_v": 12.0
    },
    "bem_settings": {
      "annulus_count": 4,
      "annulus_settings": {
        "angle_tolerance_rad": 1e-10,
        "bracket_samples": 16,
        "include_root_loss": false,
        "include_tip_loss": true,
        "loading_branch": "positive_only",
        "max_iterations": 100,
        "minimum_tip_loss_factor": 1e-06,
        "relative_residual_tolerance": 1e-10,
        "residual_tolerance_m2_s": 1e-08,
        "rotational_augmentation": {
          "kind": "disabled",
          "lift_curve_slope_per_rad": null,
          "maximum_absolute_alpha_rad": 0.7853981633974483,
          "maximum_chord_over_radius": 0.75,
          "model_id": "disabled",
          "source": null,
          "zero_lift_angle_rad": null
        }
      },
      "radial_domain": "station_span"
    },
    "blade_count": 3,
    "bounds": "error",
    "controls": {
      "angle_atol_rad": 1e-08,
      "hinge_velocity_atol_rad_s": 1e-08,
      "max_duration_s": 2.0,
      "max_input_knots": 256,
      "max_rhs_evaluations": 12000,
      "max_samples": 5000,
      "max_step_s": 0.002,
      "rtol": 1e-06,
      "shaft_speed_atol_rad_s": 1e-06
    },
    "derived_cg_distance_m": 0.01,
    "derived_hinge_inertia_kg_m2": 1.0000000000000002e-06,
    "derived_mass_kg": 0.01,
    "draft_sha256": "b3d3fd8e58a2476937607e04ecd2651b91cfb4c95c44ea026a39eff57dc167d6",
    "dry_friction": {
      "coulomb_torque_nm": 0.0,
      "mode": "none",
      "source": "explicit_frictionless_model",
      "transition_velocity_rad_s": 0.0
    },
    "dynamics_implementation_id": "cmm2_planar_projected_rate_independent_coupling_v1",
    "environment": {
      "air_density_kg_m3": 1.18,
      "dynamic_viscosity_pa_s": 1.79e-05,
      "forward_speed_m_s": 4.0,
      "id": "screen",
      "pressure_pa": 100000.0,
      "temperature_k": 293.15
    },
    "full_propeller_clearance": null,
    "hash_identity_scope": "content_identity_not_authentication_correctness_or_physical_validity",
    "hinge_radius_m": 0.085,
    "initial_angle_rad": -0.2,
    "initial_angular_velocity_rad_s": 0.01,
    "initial_omega_rad_s": 41.88790204786391,
    "interblade_clearance": null,
    "lower_stop_rad": -3.141592653589793,
    "mass_distribution": {
      "classification": "synthetic_test_fixture",
      "samples": [
        {
          "distance_from_hinge_m": 0.01,
          "intrinsic_inertia": 0.0,
          "mass_kg": 0.01,
          "source": "synthetic tip mass"
        }
      ],
      "source": "synthetic-tip"
    },
    "mechanical_source": "explicit fixture",
    "model_class": "coupled_aero_hinge_screening_only",
    "motor": {
      "current_max_a": 80.0,
      "iron_loss_exponent": 0.0,
      "kv_rpm_per_v": 1000.0,
      "magnetic_lag_tau": 0.0,
      "no_load_current_a": 1.0,
      "no_load_current_linear": 0.0,
      "no_load_current_quadratic": 0.0,
      "no_load_voltage_v": 10.0,
      "resistance_ohm": 0.05,
      "resistance_quadratic": 0.0,
      "torque_constant_kv_ratio": 1.0
    },
    "motor_binding": {
      "canonical_id": "cmm1_pr07_motor_algebra_v1",
      "dynamic_current_state": false,
      "law": "pr07_algebraic",
      "regeneration": false
    },
    "physical_qualification": false,
    "planar_load_contract": {
      "distributed_couple_model": "none",
      "foldable_bem_schema_version": 1,
      "hinge_rate_aerodynamic_model": "ignored_rate_independent_quasi_steady",
      "load_mapping_model": "planar_projected_material_load_v1",
      "projection_model": "radial_cosine_v1",
      "qualification": "screening_only_projected_rate_independent",
      "schema_version": 1,
      "sectional_aerodynamic_couple": "excluded_in_v1"
    },
    "polars": {
      "anchors": [
        {
          "family": {
            "airfoil_id": "NACA0012",
            "tables": [
              {
                "airfoil_id": "NACA0012",
                "alpha_rad": [
                  -3.1415926535897936,
                  0.0,
                  3.1415926535897936
                ],
                "cd": [
                  0.02,
                  0.02,
                  0.02
                ],
                "cl": [
                  0.6,
                  0.6,
                  0.6
                ],
                "cm": [
                  0.0,
                  0.0,
                  0.0
                ],
                "mach": 0.0,
                "metadata": {
                  "classification": "synthetic_test_fixture",
                  "experimental_validation": false,
                  "owner": "PyFoldable",
                  "physical_qualification": false,
                  "purpose": "C2V09-28 source-domain verification only",
                  "revision": "c2v09-28-synthetic-polar-v1"
                },
                "reynolds": 1.0,
                "scenario_id": "cmm2",
                "source": "pyfoldable:first-party:c2v09-28-synthetic-polar-v1"
              },
              {
                "airfoil_id": "NACA0012",
                "alpha_rad": [
                  -3.1415926535897936,
                  0.0,
                  3.1415926535897936
                ],
                "cd": [
                  0.02,
                  0.02,
                  0.02
                ],
                "cl": [
                  0.6,
                  0.6,
                  0.6
                ],
                "cm": [
                  0.0,
                  0.0,
                  0.0
                ],
                "mach": 0.0,
                "metadata": {
                  "classification": "synthetic_test_fixture",
                  "experimental_validation": false,
                  "owner": "PyFoldable",
                  "physical_qualification": false,
                  "purpose": "C2V09-28 source-domain verification only",
                  "revision": "c2v09-28-synthetic-polar-v1"
                },
                "reynolds": 1000000.0,
                "scenario_id": "cmm2",
                "source": "pyfoldable:first-party:c2v09-28-synthetic-polar-v1"
              },
              {
                "airfoil_id": "NACA0012",
                "alpha_rad": [
                  -3.1415926535897936,
                  0.0,
                  3.1415926535897936
                ],
                "cd": [
                  0.02,
                  0.02,
                  0.02
                ],
                "cl": [
                  0.6,
                  0.6,
                  0.6
                ],
                "cm": [
                  0.0,
                  0.0,
                  0.0
                ],
                "mach": 0.2,
                "metadata": {
                  "classification": "synthetic_test_fixture",
                  "experimental_validation": false,
                  "owner": "PyFoldable",
                  "physical_qualification": false,
                  "purpose": "C2V09-28 source-domain verification only",
                  "revision": "c2v09-28-synthetic-polar-v1"
                },
                "reynolds": 1.0,
                "scenario_id": "cmm2",
                "source": "pyfoldable:first-party:c2v09-28-synthetic-polar-v1"
              },
              {
                "airfoil_id": "NACA0012",
                "alpha_rad": [
                  -3.1415926535897936,
                  0.0,
                  3.1415926535897936
                ],
                "cd": [
                  0.02,
                  0.02,
                  0.02
                ],
                "cl": [
                  0.6,
                  0.6,
                  0.6
                ],
                "cm": [
                  0.0,
                  0.0,
                  0.0
                ],
                "mach": 0.2,
                "metadata": {
                  "classification": "synthetic_test_fixture",
                  "experimental_validation": false,
                  "owner": "PyFoldable",
                  "physical_qualification": false,
                  "purpose": "C2V09-28 source-domain verification only",
                  "revision": "c2v09-28-synthetic-polar-v1"
                },
                "reynolds": 1000000.0,
                "scenario_id": "cmm2",
                "source": "pyfoldable:first-party:c2v09-28-synthetic-polar-v1"
              }
            ]
          },
          "r_over_R": 0.2
        },
        {
          "family": {
            "airfoil_id": "NACA0012",
            "tables": [
              {
                "airfoil_id": "NACA0012",
                "alpha_rad": [
                  -3.1415926535897936,
                  0.0,
                  3.1415926535897936
                ],
                "cd": [
                  0.02,
                  0.02,
                  0.02
                ],
                "cl": [
                  0.6,
                  0.6,
                  0.6
                ],
                "cm": [
                  0.0,
                  0.0,
                  0.0
                ],
                "mach": 0.0,
                "metadata": {
                  "classification": "synthetic_test_fixture",
                  "experimental_validation": false,
                  "owner": "PyFoldable",
                  "physical_qualification": false,
                  "purpose": "C2V09-28 source-domain verification only",
                  "revision": "c2v09-28-synthetic-polar-v1"
                },
                "reynolds": 1.0,
                "scenario_id": "cmm2",
                "source": "pyfoldable:first-party:c2v09-28-synthetic-polar-v1"
              },
              {
                "airfoil_id": "NACA0012",
                "alpha_rad": [
                  -3.1415926535897936,
                  0.0,
                  3.1415926535897936
                ],
                "cd": [
                  0.02,
                  0.02,
                  0.02
                ],
                "cl": [
                  0.6,
                  0.6,
                  0.6
                ],
                "cm": [
                  0.0,
                  0.0,
                  0.0
                ],
                "mach": 0.0,
                "metadata": {
                  "classification": "synthetic_test_fixture",
                  "experimental_validation": false,
                  "owner": "PyFoldable",
                  "physical_qualification": false,
                  "purpose": "C2V09-28 source-domain verification only",
                  "revision": "c2v09-28-synthetic-polar-v1"
                },
                "reynolds": 1000000.0,
                "scenario_id": "cmm2",
                "source": "pyfoldable:first-party:c2v09-28-synthetic-polar-v1"
              },
              {
                "airfoil_id": "NACA0012",
                "alpha_rad": [
                  -3.1415926535897936,
                  0.0,
                  3.1415926535897936
                ],
                "cd": [
                  0.02,
                  0.02,
                  0.02
                ],
                "cl": [
                  0.6,
                  0.6,
                  0.6
                ],
                "cm": [
                  0.0,
                  0.0,
                  0.0
                ],
                "mach": 0.2,
                "metadata": {
                  "classification": "synthetic_test_fixture",
                  "experimental_validation": false,
                  "owner": "PyFoldable",
                  "physical_qualification": false,
                  "purpose": "C2V09-28 source-domain verification only",
                  "revision": "c2v09-28-synthetic-polar-v1"
                },
                "reynolds": 1.0,
                "scenario_id": "cmm2",
                "source": "pyfoldable:first-party:c2v09-28-synthetic-polar-v1"
              },
              {
                "airfoil_id": "NACA0012",
                "alpha_rad": [
                  -3.1415926535897936,
                  0.0,
                  3.1415926535897936
                ],
                "cd": [
                  0.02,
                  0.02,
                  0.02
                ],
                "cl": [
                  0.6,
                  0.6,
                  0.6
                ],
                "cm": [
                  0.0,
                  0.0,
                  0.0
                ],
                "mach": 0.2,
                "metadata": {
                  "classification": "synthetic_test_fixture",
                  "experimental_validation": false,
                  "owner": "PyFoldable",
                  "physical_qualification": false,
                  "purpose": "C2V09-28 source-domain verification only",
                  "revision": "c2v09-28-synthetic-polar-v1"
                },
                "reynolds": 1000000.0,
                "scenario_id": "cmm2",
                "source": "pyfoldable:first-party:c2v09-28-synthetic-polar-v1"
              }
            ]
          },
          "r_over_R": 1.0
        }
      ],
      "id": "cmm2-span",
      "kind": "spanwise"
    },
    "rest_angle_rad": -0.2,
    "schema_version": 1,
    "service_id": "pyfoldable.application.cmm2_coupled_transient_service",
    "service_implementation_id": "cmm2_source_bound_screening_service_v1",
    "source_identity_scope": "declared_source_hash_not_external_authentication",
    "source_sha256": "61048f3143ad1074e7e1e822b847cb7a93ba27315c9676d8b1dc43936439736e",
    "spring_stiffness_nm_rad": 0.0,
    "surface_path_clearance": null,
    "system": {
      "resistance_ohm": 0.01
    },
    "throttle": 0.1,
    "upper_stop_rad": 0.0,
    "viscous_damping_nm_s_rad": 0.0
  },
  "inherited_candidate": "C2V09-28",
  "inherited_candidate_manifest_sha256": "c2061c293190a5fec947230b89c98c553da22aab738b6146c54fd49955dfb547",
  "selection_policy": "prc_c2v09_ordered_candidates_v3_proposed",
  "source_recipe": {
    "base": "4cf0d0ea017fa824ba8d4a063ceddd015dae09d6",
    "classification": "synthetic_test_fixture",
    "continuation_interval_r_over_R": [
      0.98,
      1.0
    ],
    "experimental_validation": false,
    "id": "c2v09-29-synthetic-constant-terminal-v1",
    "law": "constant preceding-station chord/twist/airfoil; inherited literal parser",
    "owner": "PyFoldable",
    "parent_candidate": "C2V09-28",
    "parent_candidate_manifest_sha256": "c2061c293190a5fec947230b89c98c553da22aab738b6146c54fd49955dfb547",
    "parent_canonical_source_sha256": "a3852e5d14f433528fa9ad63bae26dd076b5136eacf4a7860ef76971eec2afdc",
    "parent_draft_sha256": "94553fbeaf4f41a01ee998cb51f13bc6fc34ac2ceecdf8b6d482cd63ea03c3f0",
    "physical_qualification": false,
    "status": "PROPOSED / NOT FROZEN / NOT IMPLEMENTED",
    "terminal_station_toml": "[[blade.stations]]\nr_over_R = 1.0\nchord = \"7.04 mm\"\ntwist = \"5.0 deg\"\nairfoil = \"NACA0012\"\n"
  }
}
```

## Appendix B. Pure declaration recipe

This recipe parses/seals only, with base4cf and inherited28 manifest check.
It must not be mistaken for a source/trajectory measurement.

```python
"""Pure declaration construction: parsing/sealing only, no source evaluation."""
import dataclasses, hashlib, importlib.util, json, sys
from pathlib import Path

BASE='4cf0d0ea017fa824ba8d4a063ceddd015dae09d6'
POLICY='prc_c2v09_ordered_candidates_v3_proposed'
TERMINAL='[[blade.stations]]\nr_over_R = 1.0\nchord = "7.04 mm"\ntwist = "5.0 deg"\nairfoil = "NACA0012"\n'
def canonical(x):
    if isinstance(x,float): return {'binary64':x.hex()}
    if isinstance(x,dict): return {k:canonical(v) for k,v in x.items()}
    if isinstance(x,(tuple,list)): return [canonical(v) for v in x]
    return x
def encoded(x):
    return json.dumps(canonical(x),sort_keys=True,separators=(',',':'),ensure_ascii=True,allow_nan=False).encode()
def digest(x): return hashlib.sha256(encoded(x)).hexdigest()
def build(root):
    # Read the prior manifest from the committed documentation, not a mutable fixture.
    import re
    text=(root/'docs/cmm2_numerical_feasibility_amendment.md').read_text()
    old=json.loads(re.findall(r'```json\n(.*?)```',text,re.S)[0])
    assert digest(old)=='c2061c293190a5fec947230b89c98c553da22aab738b6146c54fd49955dfb547'
    spec=importlib.util.spec_from_file_location('candidate_source',root/'tests/application/test_cmm2_coupled_transient_service.py')
    fixture=importlib.util.module_from_spec(spec); spec.loader.exec_module(fixture)
    from pyfoldable.core.models import PolarTable
    from pyfoldable.core.polar import PolarFamily
    from pyfoldable.core.polar_spanwise import SpanwisePolarAnchor,SpanwisePolarSchedule
    from pyfoldable.application.design_draft import DesignDraftArtifact
    from pyfoldable.application.mechanism_binding import _load_draft
    from pyfoldable.application.cmm2_coupled_transient_service import validate_cmm2_coupled_binding
    polar=old['effective_binding']['polars']
    anchors=[]
    for anchor in polar['anchors']:
        tables=[]
        for row in anchor['family']['tables']:
            v=dict(row)
            for name in ('alpha_rad','cl','cd','cm'): v[name]=tuple(v[name])
            tables.append(PolarTable(**v))
        anchors.append(SpanwisePolarAnchor(anchor['r_over_R'],PolarFamily(tuple(tables))))
    schedule=SpanwisePolarSchedule(polar['id'],tuple(anchors))
    source_recipe={
        'id':'c2v09-29-synthetic-constant-terminal-v1',
        'owner':'PyFoldable','classification':'synthetic_test_fixture',
        'base':BASE,'parent_candidate':'C2V09-28',
        'parent_candidate_manifest_sha256':digest(old),
        'parent_draft_sha256':old['effective_binding']['draft_sha256'],
        'parent_canonical_source_sha256':old['effective_binding']['source_sha256'],
        'terminal_station_toml':TERMINAL,
        'continuation_interval_r_over_R':[0.98,1.0],
        'law':'constant preceding-station chord/twist/airfoil; inherited literal parser',
        'physical_qualification':False,'experimental_validation':False,
        'status':'PROPOSED / NOT FROZEN / NOT IMPLEMENTED',
    }
    source_sha=digest(source_recipe)
    toml=old['draft_toml']
    toml=toml.replace('id = "TIP_HINGED_250_CANONICAL_DRAFT"','id = "C2V09_29_SYNTHETIC_TERMINAL_DRAFT"',1)
    toml=toml.replace('description = "Unqualified UI draft derived from TIP_HINGED_250_CANONICAL"','description = "First-party synthetic constant terminal continuation of C2V09-28 for numerical verification only"',1)
    toml=toml.replace('[[airfoils]]',TERMINAL+'\n[[airfoils]]',1)
    toml=toml.replace('source_design_id = "TIP_HINGED_250_CANONICAL"','source_design_id = "c2v09-29-synthetic-constant-terminal-v1"',1)
    toml=toml.replace('source_design_sha256 = "'+old['effective_binding']['source_sha256']+'"','source_design_sha256 = "'+source_sha+'"',1)
    toml += 'synthetic_geometry_owner = "PyFoldable"\nsynthetic_geometry_classification = "synthetic_test_fixture"\nsynthetic_geometry_id = "c2v09-29-synthetic-constant-terminal-v1"\nsynthetic_geometry_interval = "r_over_R=[0.98,1.0]"\nsynthetic_geometry_law = "constant preceding-station literal chord/twist/airfoil"\nsynthetic_geometry_status = "PROPOSED / NOT FROZEN / NOT IMPLEMENTED"\nsynthetic_geometry_experimental_validation = false\nsynthetic_geometry_physical_qualification = false\n'
    toml += 'inherited_candidate28_manifest_sha256 = "'+digest(old)+'"\ninherited_candidate28_draft_sha256 = "'+old['effective_binding']['draft_sha256']+'"\ninherited_canonical_source_sha256 = "'+old['effective_binding']['source_sha256']+'"\n'
    draft=DesignDraftArtifact('C2V09_29_SYNTHETIC_TERMINAL_DRAFT.toml',toml,source_sha,hashlib.sha256(toml.encode()).hexdigest())
    design=_load_draft(draft)
    old_design=_load_draft(DesignDraftArtifact('candidate28.toml',old['draft_toml'],old['effective_binding']['source_sha256'],old['effective_binding']['draft_sha256']))
    assert design.blade.stations[:-1]==old_design.blade.stations
    assert design.blade.stations[-1].r_over_R==1.0
    assert design.blade.stations[-1].chord_m==old_design.blade.stations[-1].chord_m
    assert design.blade.stations[-1].twist_rad==old_design.blade.stations[-1].twist_rad
    binding=fixture._binding(draft=draft,initial_angular_velocity_rad_s=0.01,polars=schedule)
    validate_cmm2_coupled_binding(binding)
    payload=json.loads(binding.context_json)
    changed={k for k in payload if payload[k]!=old['effective_binding'][k]}
    assert changed=={'draft_sha256','source_sha256'},changed
    manifest={'candidate_id':'C2V09-29','selection_policy':POLICY,'base':BASE,
        'inherited_candidate':'C2V09-28','inherited_candidate_manifest_sha256':digest(old),
        'source_recipe':source_recipe,'draft_toml':toml,'effective_binding':payload}
    return fixture,binding,manifest,design

if __name__=='__main__':
    root=Path(sys.argv[1]).resolve()
    fixture,binding,manifest,design=build(root)
    Path('/tmp/candidate29_manifest.json').write_text(json.dumps(manifest,sort_keys=True,indent=2,allow_nan=False)+'\n')
    Path('/tmp/candidate29_declaration_digests.json').write_text(json.dumps({
        'candidate29_manifest_sha256':digest(manifest),'synthetic_source_recipe_sha256':digest(manifest['source_recipe']),
        'candidate29_draft_sha256':binding.draft.draft_sha256,'main_v1_preflight_seal_sha256':binding.input_sha256,
        'declaration_recipe_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        'source_calls':0,'trajectory_calls':0,
        'terminal_station_parsed':dataclasses.asdict(design.blade.stations[-1]),
        'terminal_station_parsed_hex':{'chord_m':design.blade.stations[-1].chord_m.hex(),'twist_rad':design.blade.stations[-1].twist_rad.hex()},
    },sort_keys=True,indent=2)+'\n')
    print(Path('/tmp/candidate29_declaration_digests.json').read_text())
```

## Appendix C. Conditional exact-rational source certificate recipe

No source calls; all computed output endpoints are Fraction bounds. Runtime
hypotheses must be checked at actual later emitted calls.

```python
"""A priori conditional four-dimensional interval certificate; no BEM calls."""
from fractions import Fraction as F
import math, json, hashlib
EPS=F(1,2**40)
def fraction(v):return F.from_float(v) if isinstance(v,float) else F(v)
def down(v):
    f=float(v)
    if fraction(f)>v:f=math.nextafter(f,-math.inf)
    return fraction(f)
def up(v):
    f=float(v)
    if fraction(f)<v:f=math.nextafter(f,math.inf)
    return fraction(f)
def out(a,b):return (down(a),up(b))
def point(v):q=fraction(v);return(q,q)
def add(a,b):return out(a[0]+b[0],a[1]+b[1])
def sub(a,b):return out(a[0]-b[1],a[1]-b[0])
def mul(a,b):
    q=[x*y for x in a for y in b];return out(min(q),max(q))
def div(a,b):
    assert b[0]>0
    q=[x/y for x in a for y in b];return out(min(q),max(q))
def sqr_bounds(q):
    assert q>=0
    k=80;n=math.isqrt((q.numerator << (2*k))//q.denominator)
    return (F(n,2**k),F(n+1,2**k))
def merge(rows):return(min(x[0] for x in rows),max(x[1] for x in rows))
def pair_json(q):return {'lower_fraction':str(q[0]),'upper_fraction':str(q[1]),'lower_hex':float(q[0]).hex(),'upper_hex':float(q[1]).hex()}
# Parsed literals: pure algebra only; terminal proof handles correlated identity.
R=point(0.22/2.0);h=point(0.085);cosine=(F(7,8),F(1));
first=mul(point(0.2),R)
tip=add(h,mul(sub(R,h),cosine))
lower_anchor=div(first,tip);upper_anchor=point(1.0)
width=div(sub(tip,first),point(4.0))
cells=[]
for i in range(4):
    a=add(first,mul(point(i),width));b=add(first,mul(point(i+1),width))
    mid=mul(point(0.5),add(a,b));q=div(mid,tip)
    annulus_radius=mul(q,tip) # solve_bem_annulus recomputes radius
    assert q[0]>lower_anchor[1] and q[1]<1
    assert annulus_radius[0]>fraction(0.016) and annulus_radius[1]<tip[0]
    cells.append({'index':i,'inner':pair_json(a),'outer':pair_json(b),'midpoint':pair_json(mid),'span_query':pair_json(q),'annulus_radius':pair_json(annulus_radius)})
# Source _station_at_hinge operations, independently applied to parsed SI.
nominal=[(0.2,0.024640000000000002,0.5410520681182421),(0.4,0.02288,0.4188790204786392),(0.6,0.02024,0.29670597283903605),(0.8,0.014960000000000001,0.17453292519943295),(0.98,0.00704,0.08726646259971647),(1.0,0.00704,0.08726646259971647)]
hinge_ratio=0.085/(0.22/2.0);w=(hinge_ratio-0.6)/(0.8-0.6)
inserted=(hinge_ratio,nominal[2][1]+w*(nominal[3][1]-nominal[2][1]),nominal[2][2]+w*(nominal[3][2]-nominal[2][2]))
stations=sorted(nominal+[inserted]);weight=(F(0),F(1))
# Every successful interpolation branch has stored weight in [0,1] by monotonic RN.
chord=merge([add(point(a[1]),mul(weight,sub(point(b[1]),point(a[1])))) for a,b in zip(stations,stations[1:])])
twist=merge([add(point(a[2]),mul(weight,sub(point(b[2]),point(a[2])))) for a,b in zip(stations,stations[1:])])
assert chord[0]>fraction(0.001) and chord[1]<fraction(0.1)
assert twist[0]>F(-3,2) and twist[1]<F(3,2)
# Hypotheses: actual emitted s,c nonnegative, s^2+c^2 <=1+EPS;
# E and W emitted hypot results differ <=EPS from exact Euclidean norms.
# Source scalar RN operation magnitudes <128: each rounding error <2^-46;
# vector arithmetic contribution <EPS. No universal libm theorem is assumed.
U=mul((fraction(100.0*math.pi/30.0),F(600)),(fraction(0.016),R[1]))
E_norm_hi=sqr_bounds(F(16)+U[1]*U[1])[1]
E_hi=E_norm_hi+EPS
W_hi=(E_norm_hi+E_hi*(1+EPS))/2+3*EPS
assert W_hi<F(67)
W=(F(2)-EPS,W_hi)
# Sound sqrt: source multiplication RN intervals and measured sqrt error<=EPS.
sound_square=mul(mul(point(1.4),point(287.05)),point(293.15))
sound=(sqr_bounds(sound_square[0])[0]-EPS,sqr_bounds(sound_square[1])[1]+EPS)
mach=div(W,sound)
reynolds=div(mul(mul(point(1.18),W),(fraction(0.001),fraction(0.1))),point(1.79e-5))
phi=(F(0),fraction(float.fromhex('0x1.921fb54442d19p+0')))
alpha=sub((F(-3,2),F(3,2)),phi)
assert mach[0]>=0 and mach[1]<fraction(0.2)
assert reynolds[0]>1 and reynolds[1]<1000000
assert alpha[0]>fraction(-float.fromhex('0x1.921fb54442d19p+1')) and alpha[1]<fraction(float.fromhex('0x1.921fb54442d19p+1'))
certificate={'type':'A_PRIORI_CONDITIONAL_NOT_MEASURED','epsilon_libm_hypothesis':str(EPS),'projection_factor':pair_json(cosine),'effective_tip':pair_json(tip),'projected_lower_anchor':pair_json(lower_anchor),'projected_upper_anchor':pair_json(upper_anchor),'cells':cells,'chord':pair_json(chord),'twist':pair_json(twist),'W':pair_json(out(*W)),'sound_speed':pair_json(out(*sound)),'mach':pair_json(mach),'reynolds':pair_json(reynolds),'alpha':pair_json(alpha),'span_lower_margin_fraction':str(min(F.from_float(float.fromhex(c['span_query']['lower_hex']))-lower_anchor[1] for c in cells)),'span_upper_margin_fraction':str(min(1-F.from_float(float.fromhex(c['span_query']['upper_hex'])) for c in cells))}
if __name__=='__main__':
    print(json.dumps(certificate,sort_keys=True,indent=2))
```
