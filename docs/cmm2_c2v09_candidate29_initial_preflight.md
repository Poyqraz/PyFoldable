# Candidate29 initial-only measured preflight record

Status: **PROPOSED / NOT FROZEN / NOT IMPLEMENTED / NOT SELECTED**.

[Complete declaration](cmm2_c2v09_candidate29_proposal.md) was committed at
`33a59142f0206e1370c9a0c44116f1dd709b35d3` and independently approved for
initial-only measurements before the first source call. The reviewer reproduced
literal parsing, seals, Fraction interval bounds and hashes with zero source
calls. This record follows that approval; no trajectory was run.

Runtime: Python3.12.14, NumPy2.3.5, SciPy1.17.0, glibc2.39, Linux x86_64.
All21 production implementation files were byte-hash checked against base
`4cf0d0ea017fa824ba8d4a063ceddd015dae09d6`; full paths/hashes below. This is
**main-v1 initial preflight**, not future Radau/v2 evidence. Local1.17.0 source
observations are not SciPy1.15.3/1.17.1 CI evidence. The actual fixture source
is the unchanged base test module; it supplies the declared binding only,
not an independent mechanical/reference equation oracle.

## Results and limits

| Requirement | Initial result |
| --- | --- |
| Real motor/BEM/mapper | PASS; one motor and three fresh BEM/map calls in completed run |
| Mach/Reynolds/alpha/span coverage | PASS under explicit conditional hypotheses;43 logical queries per call,129 checked |
| Terminal coverage | Effective/source radius0.10950166444603104 m; normalization false, original radius retained, delta0 |
| Independent represented Q2 | PASS; exact Fraction residual/inverse and factor-two branch, both row eta0 |
| Hinge-load detectability |91.7347827074291 rad/s² > B_abs_correct1.0588342316166035e-11 rad/s²: PASS |
| Raw-versus-mapped detectability |362.97299702022957 rad/s² > same B_abs_correct: PASS |
| Independent hinge work |8.080095669630529e-7 W > U_P09=9.86666666666667e-8 W: PASS |
| Fold/shaft margins |1.3707963267948966 rad and31.41592653589793 rad/s: PASS |
| Actual repeated BEM/map Q4 | PASS; changed real state/index and actual table metadata, finite byte-identical outputs |
| Literal partition predicate | **FAIL / BLOCKED**: structural mapped edges have zero distance to hinge-cell endpoints |
| Selection / v2 seal / trajectory / freeze | NOT ESTABLISHED / NOT PRODUCED / NOT RUN / NOT AUTHORIZED |

All four source dimensions are recorded below with hex intervals, projected
anchors/stations, actual binary64 radial cells and actual query weights. Pure
postprocessing independently reconstructed each station interpolation with
weight in[0,1], matching emitted chord/twist and recomputed annulus radius
exactly. In cell1, midpoint0.05481312416726164 and kernel's ratio*tip radius
0.05481312416726165 differ by one ULP; they are recorded separately. This is
not a coverage failure and neither is silently substituted for the other.
The maximum measured hypot/sound-sqrt exact enclosure error is
9.658776289286476e-15, below the declared conditional2^-40 bound. Actual
initial checks pass; states/runtime outside those hypotheses remain unproven.

The mapper splits the hinge-containing cell at h=0.085. Source hinge-cell
endpoints are0.06575083222301552 and0.08762624833452329 m. Mapped interval2
inner/interval1 outer equal the first; interval4 inner/interval3 outer equal
the second. Their exact Fraction distance is0, while frozen uncertainty is
1.043014874852491e-9 m. The hinge itself has positive margin0.0026262483345232818 m.
We retain the literal all-edge failure and do not exempt own boundaries or
replace the fixture. Whether the frozen wording intended a different identity-
aware partition predicate requires separate independent contract review;
**no amended partition rule is proposed or applied here**. No candidate29
selection or freeze readiness follows. Candidate28 remains a mapper rejection.

Q4 table metadata delta is exactly the declaration's
`q4_probe="candidate29-q4-metadata-v1"` on each table. Main-v1 variant seal
is `eabbfcf107fea16b0c17d281edb167be9d49c22ffeb64e5c0618f7a865ace931`.
State IDs cmm2-0/cmm2-1 enter real FoldableBEM, projected schedule IDs change
accordingly, and each returned source object enters the real mapper. The
actual additional table metadata enters real BEM; differing report IDs are
not the evidence. All three measured triples (thrust,Q_phi,q_theta) encode
`3f9356e4d5005aa8`, `bf614c163fd74ce0`, `befc3df27cec3853`.

Two initial scratch-observer attempts had AttributeErrors in observer field
names, retained below with scripts/record hashes and partial source results.
Only instrumentation was corrected; the committed candidate, controls,
coefficients, physical state, preflight rules and gates were identical.
Across all attempts:3 motor,7 BEM,6 real mapper, **0 trajectory** calls. The
completed run has3/3 BEM/map calls. The script does not call an integrator.
These errors are not concealed as candidate failures or successful preflights.

## Mathematical audit

The independent assembly uses N3,m0.01,h0.085,c0.01,J=m*c²,I0=1e-4,
C=m*h*c, A=J+m*h²+2*C*cos(theta), B=J+C*cos(theta),
M=[[I0+N*A,N*B],[N*B,N*J]]. Fresh motor and mapped signed loads assemble b;
q_theta-zero and raw-positive-torque mutants are independently assembled.
The production acceleration is the subject only. No production mass/Schur or
power_identity is called as an oracle. All represented floats are converted
directly to Fraction; Q2 residual is b−M*x_prod, not decimal reconstruction.
The independent energy derivative is

```text
E_dot_ref = (M00*omega+M01*v)*omega_dot_ref
          + (M01*omega+M11*v)*theta_ddot_ref
          - N*C*sin(theta)*(omega²+omega*v)*v
          + N*k*(theta-theta_rest)*v
```

Here k=0 and Qh/damping/friction0; their frozen zero contributions remain.
The exact represented inverse supplies reference accelerations. P_scale and
U_P09 retain the frozen relative and64-ULP formula, no fitted threshold.
All rational numerators/denominators and row/relative results are below.

## Review/acceptance sequence

This is an initial feasibility observation, not a canonical ordered full walk.
It establishes neither v2 preflight nor trajectory verification. Current frozen
contracts remain unchanged. Resolve the partition blocker through later
independent review without measurement-driven fixture adaptation; separately
review/freeze any accepted amendment under explicit authorization. Only then
may separately authorized implementation, v2 sealing, full Phase A/B walk,
DOP853 A/B stabilization and all C2V gates proceed. Q5 runtime/partition/
minimum-SciPy characterization remains pending. PR81/84 remain Draft/BLOCKED;
ADR-009 NOT CREATED/NOT ACCEPTED; physical_qualification=false; PR-06C
unresolved; GEOM/calibration/experimental validation NONE.

## Published numeric record

The JSON retains the full baseline BEM/map outputs and43 baseline queries,
all numeric audits, actual repeated-call metadata/bit evidence, checked-call
extrema and source hashes. Repeated identical physical arrays and full emitted
math observations are condensed; their original scratch byte hash is recorded,
not claimed to be a CI artifact. The executable scratch recipe below specifies
capture/recomputation. This published record is itself content-addressed:

UTF-8 JSON bytes including final newline SHA256 `183eb23a8bac8c4add42f76539f219c5726b36a613297d5bb7e4c83a331780c9`.

```json
{
  "actual_bem_calls": 3,
  "actual_mapper_calls": 3,
  "all_initial_requirements_pass": false,
  "bem": [
    {
      "effective_geometry": {
        "blade_count": 3,
        "diameter_m": 0.2190033288920621,
        "hub_radius_m": 0.016,
        "radius_m": 0.10950166444603104,
        "stations": [
          {
            "airfoil_id": "NACA0012",
            "chord_m": 0.024640000000000002,
            "r_over_R": 0.2009101880898159,
            "radius_m": 0.022000000000000002,
            "twist_rad": 0.5410520681182421
          },
          {
            "airfoil_id": "NACA0012",
            "chord_m": 0.02288,
            "r_over_R": 0.4018203761796318,
            "radius_m": 0.044000000000000004,
            "twist_rad": 0.4188790204786392
          },
          {
            "airfoil_id": "NACA0012",
            "chord_m": 0.02024,
            "r_over_R": 0.6027305642694476,
            "radius_m": 0.066,
            "twist_rad": 0.29670597283903605
          },
          {
            "airfoil_id": "NACA0012",
            "chord_m": 0.01568,
            "r_over_R": 0.7762439085288341,
            "radius_m": 0.085,
            "twist_rad": 0.19119288624119699
          },
          {
            "airfoil_id": "NACA0012",
            "chord_m": 0.014960000000000001,
            "r_over_R": 0.8030946395053741,
            "radius_m": 0.08794019973352374,
            "twist_rad": 0.17453292519943295
          },
          {
            "airfoil_id": "NACA0012",
            "chord_m": 0.00704,
            "r_over_R": 0.9803094639505373,
            "radius_m": 0.1073455179747803,
            "twist_rad": 0.08726646259971647
          },
          {
            "airfoil_id": "NACA0012",
            "chord_m": 0.00704,
            "r_over_R": 1.0,
            "radius_m": 0.10950166444603104,
            "twist_rad": 0.08726646259971647
          }
        ]
      },
      "fixed_limit_equivalent": false,
      "nominal_geometry": {
        "blade_count": 3,
        "diameter_m": 0.22,
        "hub_radius_m": 0.016,
        "radius_m": 0.11,
        "stations": [
          {
            "airfoil_id": "NACA0012",
            "chord_m": 0.024640000000000002,
            "r_over_R": 0.2,
            "radius_m": 0.022000000000000002,
            "twist_rad": 0.5410520681182421
          },
          {
            "airfoil_id": "NACA0012",
            "chord_m": 0.02288,
            "r_over_R": 0.4,
            "radius_m": 0.044000000000000004,
            "twist_rad": 0.4188790204786392
          },
          {
            "airfoil_id": "NACA0012",
            "chord_m": 0.02024,
            "r_over_R": 0.6,
            "radius_m": 0.066,
            "twist_rad": 0.29670597283903605
          },
          {
            "airfoil_id": "NACA0012",
            "chord_m": 0.014960000000000001,
            "r_over_R": 0.8,
            "radius_m": 0.08800000000000001,
            "twist_rad": 0.17453292519943295
          },
          {
            "airfoil_id": "NACA0012",
            "chord_m": 0.00704,
            "r_over_R": 0.98,
            "radius_m": 0.10779999999999999,
            "twist_rad": 0.08726646259971647
          },
          {
            "airfoil_id": "NACA0012",
            "chord_m": 0.00704,
            "r_over_R": 1.0,
            "radius_m": 0.11,
            "twist_rad": 0.08726646259971647
          }
        ]
      },
      "polar_schedule_id": "cmm2-span@fold:cmm2-0",
      "projection_factor": 0.9800665778412416,
      "qualification": "screening_only_until_pr06c_passes",
      "rotor_result": {
        "airfoil_id": "cmm2-span@fold:cmm2-0",
        "annulus_count": 4,
        "clamped_dimensions": [],
        "elements": [
          {
            "geometry_extrapolated": false,
            "index": 0,
            "inner_radius_m": 0.022000000000000002,
            "outer_radius_m": 0.04387541611150776,
            "solution": {
              "airfoil_id": "NACA0012",
              "angle_of_attack_rad": -0.7987044060822999,
              "axial_induced_velocity_m_s": 0.04911611185674403,
              "cd": 0.02,
              "chord_m": 0.02376498335553969,
              "circulation_m2_s": 0.030142164947657195,
              "cl": 0.6000000000000001,
              "clamped_dimensions": [],
              "combined_loss_factor": 0.7717525241685829,
              "converged": true,
              "differential_thrust_n_m": 0.11536681109700814,
              "differential_torque_nm_m": 0.014373341408119203,
              "inflow_angle_rad": 1.2790158775021925,
              "interpolated_dimensions": [
                "alpha_rad",
                "mach",
                "reynolds"
              ],
              "iterations": 5,
              "loading_regime": "positive",
              "mach": 0.012317652001303844,
              "operating_condition_id": "cmm2-screen",
              "polar_bounds": "error",
              "polar_query_envelope": {
                "alpha_rad_max": -0.7583402303930604,
                "alpha_rad_min": -0.7998583085033033,
                "clamped_dimensions": [],
                "interpolated_dimensions": [
                  "alpha_rad",
                  "mach",
                  "reynolds"
                ],
                "mach_max": 0.012327693187748876,
                "mach_min": 0.012317069778330915,
                "query_count": 12,
                "reynolds_max": 6628.817318398541,
                "reynolds_min": 6623.104924420386,
                "sources": [
                  "pyfoldable:first-party:c2v09-28-synthetic-polar-v1"
                ]
              },
              "polar_sources": [
                "pyfoldable:first-party:c2v09-28-synthetic-polar-v1"
              ],
              "psi_rad": 1.3193800531914317,
              "r_over_R": 0.3007964145785889,
              "radius_m": 0.032937708055753884,
              "raw_polar_cd": 0.02,
              "raw_polar_cl": 0.6000000000000001,
              "relative_speed_m_s": 4.227812056743415,
              "residual_m2_s": 4.198030811863873e-16,
              "reynolds": 6623.417995947017,
              "root_loss_factor": 1.0,
              "rotational_augmentation": {
                "alpha_rad": -0.7987044060822999,
                "applied": false,
                "augmentation_factor": 0.0,
                "cd": 0.02,
                "cd_2d": 0.02,
                "chord_over_radius": 0.7215129636619688,
                "cl": 0.6000000000000001,
                "cl_2d": 0.6000000000000001,
                "model_id": "disabled",
                "potential_cl": null,
                "source": null
              },
              "scenario_id": "cmm2",
              "schema_version": 5,
              "settings": {
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
              "tangential_induced_velocity_m_s": 0.163528054042835,
              "tip_loss_factor": 0.7717525241685829,
              "twist_rad": 0.48031147141989267
            },
            "thrust_n": 0.002523696998204764,
            "torque_nm": 0.00031442282421537246,
            "width_m": 0.02187541611150776
          },
          {
            "geometry_extrapolated": false,
            "index": 1,
            "inner_radius_m": 0.04387541611150776,
            "outer_radius_m": 0.06575083222301552,
            "solution": {
              "airfoil_id": "NACA0012",
              "angle_of_attack_rad": -0.7263622380298839,
              "axial_induced_velocity_m_s": 0.07636054694725836,
              "cd": 0.02,
              "chord_m": 0.021582425099928602,
              "circulation_m2_s": 0.02984342403554542,
              "cl": 0.6,
              "clamped_dimensions": [],
              "combined_loss_factor": 0.7000497251038897,
              "converged": true,
              "differential_thrust_n_m": 0.21292245800718473,
              "differential_torque_nm_m": 0.02402053421695939,
              "inflow_angle_rad": 1.0851925160530775,
              "interpolated_dimensions": [
                "alpha_rad",
                "mach",
                "reynolds"
              ],
              "iterations": 5,
              "loading_regime": "positive",
              "mach": 0.013428868153714588,
              "operating_condition_id": "cmm2-screen",
              "polar_bounds": "error",
              "polar_query_envelope": {
                "alpha_rad_max": -0.6908823460540253,
                "alpha_rad_min": -0.7397339431744326,
                "clamped_dimensions": [],
                "interpolated_dimensions": [
                  "alpha_rad",
                  "mach",
                  "reynolds"
                ],
                "mach_max": 0.01343732487155341,
                "mach_min": 0.013421294116293003,
                "query_count": 11,
                "reynolds_max": 6561.90258215457,
                "reynolds_min": 6554.074219341088,
                "sources": [
                  "pyfoldable:first-party:c2v09-28-synthetic-polar-v1"
                ]
              },
              "polar_sources": [
                "pyfoldable:first-party:c2v09-28-synthetic-polar-v1"
              ],
              "psi_rad": 1.120672408028936,
              "r_over_R": 0.5005688675561349,
              "radius_m": 0.05481312416726165,
              "raw_polar_cd": 0.02,
              "raw_polar_cl": 0.6,
              "relative_speed_m_s": 4.609216974361877,
              "residual_m2_s": -2.220446049250313e-15,
              "reynolds": 6557.772879319105,
              "root_loss_factor": 1.0,
              "rotational_augmentation": {
                "alpha_rad": -0.7263622380298839,
                "applied": false,
                "augmentation_factor": 0.0,
                "cd": 0.02,
                "cd_2d": 0.02,
                "chord_over_radius": 0.39374557513032954,
                "cl": 0.6,
                "cl_2d": 0.6,
                "model_id": "disabled",
                "potential_cl": null,
                "source": null
              },
              "scenario_id": "cmm2",
              "schema_version": 5,
              "settings": {
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
              "tangential_induced_velocity_m_s": 0.14468954978764215,
              "tip_loss_factor": 0.7000497251038897,
              "twist_rad": 0.35883027802319367
            },
            "thrust_n": 0.004657767368392202,
            "torque_nm": 0.0005254591812166969,
            "width_m": 0.021875416111507756
          },
          {
            "geometry_extrapolated": false,
            "index": 2,
            "inner_radius_m": 0.06575083222301552,
            "outer_radius_m": 0.08762624833452329,
            "solution": {
              "airfoil_id": "NACA0012",
              "angle_of_attack_rad": -0.6880232455173456,
              "axial_induced_velocity_m_s": 0.09624471318750594,
              "cd": 0.02,
              "chord_m": 0.017674750333095346,
              "circulation_m2_s": 0.027189300201741644,
              "cl": 0.5999999999999999,
              "clamped_dimensions": [],
              "combined_loss_factor": 0.576897500428257,
              "converged": true,
              "differential_thrust_n_m": 0.28374219050081256,
              "differential_torque_nm_m": 0.030994455815267163,
              "inflow_angle_rad": 0.9253723301438402,
              "interpolated_dimensions": [
                "alpha_rad",
                "mach",
                "reynolds"
              ],
              "iterations": 5,
              "loading_regime": "positive",
              "mach": 0.014939489060703656,
              "operating_condition_id": "cmm2-screen",
              "polar_bounds": "error",
              "polar_query_envelope": {
                "alpha_rad_max": -0.6568307571861505,
                "alpha_rad_min": -0.699119287491291,
                "clamped_dimensions": [],
                "interpolated_dimensions": [
                  "alpha_rad",
                  "mach",
                  "reynolds"
                ],
                "mach_max": 0.01494675985554722,
                "mach_min": 0.01493339705387571,
                "query_count": 10,
                "reynolds_max": 5977.465301635404,
                "reynolds_min": 5972.121288344493,
                "sources": [
                  "pyfoldable:first-party:c2v09-28-synthetic-polar-v1"
                ]
              },
              "polar_sources": [
                "pyfoldable:first-party:c2v09-28-synthetic-polar-v1"
              ],
              "psi_rad": 0.9565648184750354,
              "r_over_R": 0.7003413205336809,
              "radius_m": 0.0766885402787694,
              "raw_polar_cd": 0.02,
              "raw_polar_cl": 0.5999999999999999,
              "relative_speed_m_s": 5.127710375787816,
              "residual_m2_s": -3.928801728392273e-14,
              "reynolds": 5974.557586230008,
              "root_loss_factor": 1.0,
              "rotational_augmentation": {
                "alpha_rad": -0.6880232455173456,
                "applied": false,
                "augmentation_factor": 0.0,
                "cd": 0.02,
                "cd_2d": 0.02,
                "chord_over_radius": 0.230474465530914,
                "cl": 0.5999999999999999,
                "cl_2d": 0.5999999999999999,
                "model_id": "disabled",
                "potential_cl": null,
                "source": null
              },
              "scenario_id": "cmm2",
              "schema_version": 5,
              "settings": {
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
              "tangential_induced_velocity_m_s": 0.12781352107069655,
              "tip_loss_factor": 0.576897500428257,
              "twist_rad": 0.23734908462649468
            },
            "thrust_n": 0.006206978485595982,
            "torque_nm": 0.000678016618108711,
            "width_m": 0.02187541611150777
          },
          {
            "geometry_extrapolated": false,
            "index": 3,
            "inner_radius_m": 0.08762624833452329,
            "outer_radius_m": 0.10950166444603104,
            "solution": {
              "airfoil_id": "NACA0012",
              "angle_of_attack_rad": -0.6708214459808689,
              "axial_induced_velocity_m_s": 0.11242437788640736,
              "cd": 0.02,
              "chord_m": 0.010624067361564756,
              "circulation_m2_s": 0.01831466054888646,
              "cl": 0.6,
              "clamped_dimensions": [],
              "combined_loss_factor": 0.35313232699110886,
              "converged": true,
              "differential_thrust_n_m": 0.25131949251576385,
              "differential_torque_nm_m": 0.02713446695846921,
              "inflow_angle_rad": 0.7975789288284206,
              "interpolated_dimensions": [
                "alpha_rad",
                "mach",
                "reynolds"
              ],
              "iterations": 5,
              "loading_regime": "positive",
              "mach": 0.01674168092621358,
              "operating_condition_id": "cmm2-screen",
              "polar_bounds": "error",
              "polar_query_envelope": {
                "alpha_rad_max": -0.6428167966358592,
                "alpha_rad_min": -0.6928931745865771,
                "clamped_dimensions": [],
                "interpolated_dimensions": [
                  "alpha_rad",
                  "mach",
                  "reynolds"
                ],
                "mach_max": 0.016748247990714147,
                "mach_min": 0.01672725305989874,
                "query_count": 10,
                "reynolds_max": 4026.0291733368513,
                "reynolds_min": 4020.982304912053,
                "sources": [
                  "pyfoldable:first-party:c2v09-28-synthetic-polar-v1"
                ]
              },
              "polar_sources": [
                "pyfoldable:first-party:c2v09-28-synthetic-polar-v1"
              ],
              "psi_rad": 0.8255835781734303,
              "r_over_R": 0.900113773511227,
              "radius_m": 0.09856395639027717,
              "raw_polar_cd": 0.02,
              "raw_polar_cl": 0.6,
              "relative_speed_m_s": 5.74628025394002,
              "residual_m2_s": -5.0133508455729725e-15,
              "reynolds": 4024.450548917323,
              "root_loss_factor": 1.0,
              "rotational_augmentation": {
                "alpha_rad": -0.6708214459808689,
                "applied": false,
                "augmentation_factor": 0.0,
                "cd": 0.02,
                "cd_2d": 0.02,
                "chord_over_radius": 0.10778856440682374,
                "cl": 0.6,
                "cl_2d": 0.6,
                "model_id": "disabled",
                "potential_cl": null,
                "source": null
              },
              "scenario_id": "cmm2",
              "schema_version": 5,
              "settings": {
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
              "tangential_induced_velocity_m_s": 0.11519711908087249,
              "tip_loss_factor": 0.35313232699110886,
              "twist_rad": 0.12675748284755173
            },
            "thrust_n": 0.005497718475715294,
            "torque_nm": 0.0005935777556804722,
            "width_m": 0.021875416111507756
          }
        ],
        "geometry_extended": false,
        "geometry_interpolation": "linear_chord_twist",
        "inner_radius_m": 0.022000000000000002,
        "integration_method": "midpoint",
        "interpolated_dimensions": [
          "alpha_rad",
          "mach",
          "reynolds"
        ],
        "maximum_residual_m2_s": 3.928801728392273e-14,
        "operating_condition_id": "cmm2-screen",
        "outer_radius_m": 0.10950166444603104,
        "polar_bounds": "error",
        "polar_query_envelope": {
          "alpha_rad_max": -0.6428167966358592,
          "alpha_rad_min": -0.7998583085033033,
          "clamped_dimensions": [],
          "interpolated_dimensions": [
            "alpha_rad",
            "mach",
            "reynolds"
          ],
          "mach_max": 0.016748247990714147,
          "mach_min": 0.012317069778330915,
          "query_count": 43,
          "reynolds_max": 6628.817318398541,
          "reynolds_min": 4020.982304912053,
          "sources": [
            "pyfoldable:first-party:c2v09-28-synthetic-polar-v1"
          ]
        },
        "polar_sources": [
          "pyfoldable:first-party:c2v09-28-synthetic-polar-v1"
        ],
        "power_coefficient": 0.5021263649707054,
        "propulsive_efficiency": 0.8541395852534771,
        "radial_domain": "station_span",
        "scenario_id": "cmm2",
        "schema_version": 5,
        "settings": {
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
        "shaft_power_w": 0.08844531574919819,
        "thrust_coefficient": 0.15654577139449707,
        "thrust_n": 0.01888616132790824,
        "torque_coefficient": 0.07991589304185288,
        "torque_nm": 0.0021114763792212526
      },
      "schema_version": 1,
      "state": {
        "angle_from_deployed_rad": -0.2,
        "deployed_angle_rad": 0.0,
        "hinge_radius_m": 0.085,
        "id": "cmm2-0",
        "opening_angle_rad": -0.2,
        "projection_model": "radial_cosine_v1"
      },
      "station_projection": [
        {
          "airfoil_id": "NACA0012",
          "chord_m": 0.024640000000000002,
          "effective_r_over_R": 0.2009101880898159,
          "effective_radius_m": 0.022000000000000002,
          "nominal_r_over_R": 0.2,
          "nominal_radius_m": 0.022000000000000002,
          "twist_rad": 0.5410520681182421
        },
        {
          "airfoil_id": "NACA0012",
          "chord_m": 0.02288,
          "effective_r_over_R": 0.4018203761796318,
          "effective_radius_m": 0.044000000000000004,
          "nominal_r_over_R": 0.4,
          "nominal_radius_m": 0.044000000000000004,
          "twist_rad": 0.4188790204786392
        },
        {
          "airfoil_id": "NACA0012",
          "chord_m": 0.02024,
          "effective_r_over_R": 0.6027305642694476,
          "effective_radius_m": 0.066,
          "nominal_r_over_R": 0.6,
          "nominal_radius_m": 0.066,
          "twist_rad": 0.29670597283903605
        },
        {
          "airfoil_id": "NACA0012",
          "chord_m": 0.01568,
          "effective_r_over_R": 0.7762439085288341,
          "effective_radius_m": 0.085,
          "nominal_r_over_R": 0.7727272727272728,
          "nominal_radius_m": 0.085,
          "twist_rad": 0.19119288624119699
        },
        {
          "airfoil_id": "NACA0012",
          "chord_m": 0.014960000000000001,
          "effective_r_over_R": 0.8030946395053741,
          "effective_radius_m": 0.08794019973352374,
          "nominal_r_over_R": 0.8,
          "nominal_radius_m": 0.08800000000000001,
          "twist_rad": 0.17453292519943295
        },
        {
          "airfoil_id": "NACA0012",
          "chord_m": 0.00704,
          "effective_r_over_R": 0.9803094639505373,
          "effective_radius_m": 0.1073455179747803,
          "nominal_r_over_R": 0.98,
          "nominal_radius_m": 0.10779999999999999,
          "twist_rad": 0.08726646259971647
        },
        {
          "airfoil_id": "NACA0012",
          "chord_m": 0.00704,
          "effective_r_over_R": 1.0,
          "effective_radius_m": 0.10950166444603104,
          "nominal_r_over_R": 1.0,
          "nominal_radius_m": 0.11,
          "twist_rad": 0.08726646259971647
        }
      ]
    }
  ],
  "candidate_disposition": "NOT SELECTED / BLOCKED: literal partition predicate; normative interpretation unresolved",
  "candidate_manifest_sha256": "0b37fb45c005d7a046dee6541d1a89e4a0a5cead7434621718c90d191843b7a4",
  "captured_audit": {
    "all_pass": true,
    "captured_file_sha256": "3ecd1c6e70fcbe98d9047dafe56044e25dee1d5e1c695cfd5d8a13e04dc55c7c",
    "interpolation_rows": [
      {
        "cell": 0,
        "chord_hex": "0x1.855d9093546a6p-6",
        "chord_m": 0.02376498335553969,
        "lower_station": 0,
        "pass": true,
        "recomputed_annulus_radius_m": 0.032937708055753884,
        "twist_hex": "0x1.ebd6c536917cdp-2",
        "twist_rad": 0.48031147141989267,
        "upper_station": 1,
        "weight": 0.4971685479888127,
        "weight_hex": "0x1.fd19c078d8d6ep-2"
      },
      {
        "cell": 1,
        "chord_hex": "0x1.619b407e3e786p-6",
        "chord_m": 0.021582425099928602,
        "lower_station": 1,
        "pass": true,
        "recomputed_annulus_radius_m": 0.05481312416726165,
        "twist_hex": "0x1.6f713453b262ap-2",
        "twist_rad": 0.35883027802319367,
        "upper_station": 2,
        "weight": 0.49150564396643825,
        "weight_hex": "0x1.f74d416a8a84cp-2"
      },
      {
        "cell": 2,
        "chord_hex": "0x1.219546a951ab0p-6",
        "chord_m": 0.017674750333095346,
        "lower_station": 2,
        "pass": true,
        "recomputed_annulus_radius_m": 0.0766885402787694,
        "twist_hex": "0x1.e61746e1a690ep-3",
        "twist_rad": 0.23734908462649468,
        "upper_station": 3,
        "weight": 0.5625547515141788,
        "weight_hex": "0x1.20072d27ecf4bp-1"
      },
      {
        "cell": 3,
        "chord_hex": "0x1.5c2122ef2870bp-7",
        "chord_m": 0.010624067361564756,
        "lower_station": 4,
        "pass": true,
        "recomputed_annulus_radius_m": 0.09856395639027717,
        "twist_hex": "0x1.03996d5ad4000p-3",
        "twist_rad": 0.12675748284755173,
        "upper_station": 5,
        "weight": 0.5474662422266723,
        "weight_hex": "0x1.184d7ecc0e1dep-1"
      }
    ],
    "source_calls": 0,
    "source_files_equal_base": [
      "pyfoldable/application/cmm2_coupled_transient_service.py",
      "pyfoldable/application/coupled_transient_service.py",
      "pyfoldable/application/folding_mechanism.py",
      "pyfoldable/application/mechanism_binding.py",
      "pyfoldable/core/airfoil.py",
      "pyfoldable/core/bem.py",
      "pyfoldable/core/bem_rotor.py",
      "pyfoldable/core/config.py",
      "pyfoldable/core/foldable_aero_load.py",
      "pyfoldable/core/foldable_rotor.py",
      "pyfoldable/core/models.py",
      "pyfoldable/core/motor_bem_coupling.py",
      "pyfoldable/core/polar.py",
      "pyfoldable/core/polar_spanwise.py",
      "pyfoldable/core/rotational_augmentation.py",
      "pyfoldable/core/units.py",
      "pyfoldable/dynamics/cmm2_coupled_transient.py",
      "pyfoldable/dynamics/coupled_transient.py",
      "pyfoldable/dynamics/mechanism_contracts.py",
      "pyfoldable/dynamics/mechanism_transient.py",
      "pythrust/propulsion/models.py"
    ],
    "trajectory_calls": 0
  },
  "code_base": "4cf0d0ea017fa824ba8d4a063ceddd015dae09d6",
  "coverage": {
    "check_count": 593,
    "conditional_hypotheses_pass": true,
    "effective_tip_m": 0.10950166444603104,
    "emitted_math_record_scope": "full scratch record SHA binds observations; published extrema/check count and executable observing recipe; not CI evidence",
    "epsilon": {
      "approx": 9.094947017729282e-13,
      "fraction": "1/1099511627776"
    },
    "field_intervals": [
      {
        "geometry_extrapolated": false,
        "inner_projected_radius_m": 0.022000000000000002,
        "one_blade_shaft_generalized_load_nm": -0.00010480760807179081,
        "one_tip_hinge_generalized_torque_nm": 0.0,
        "outer_projected_radius_m": 0.04387541611150776,
        "role": "fixed_root",
        "source_differential_thrust_n_m": 0.11536681109700814,
        "source_differential_torque_nm_m": 0.014373341408119203,
        "source_index": 0,
        "thrust_density_measure": "whole_rotor_newton_per_projected_radial_metre",
        "torque_density_measure": "whole_rotor_newton_metre_per_projected_radial_metre",
        "whole_rotor_resisting_torque_nm": 0.00031442282421537246,
        "whole_rotor_thrust_n": 0.002523696998204764
      },
      {
        "geometry_extrapolated": false,
        "inner_projected_radius_m": 0.04387541611150776,
        "one_blade_shaft_generalized_load_nm": -0.00017515306040556558,
        "one_tip_hinge_generalized_torque_nm": 0.0,
        "outer_projected_radius_m": 0.06575083222301552,
        "role": "fixed_root",
        "source_differential_thrust_n_m": 0.21292245800718473,
        "source_differential_torque_nm_m": 0.02402053421695939,
        "source_index": 1,
        "thrust_density_measure": "whole_rotor_newton_per_projected_radial_metre",
        "torque_density_measure": "whole_rotor_newton_metre_per_projected_radial_metre",
        "whole_rotor_resisting_torque_nm": 0.0005254591812166969,
        "whole_rotor_thrust_n": 0.004657767368392202
      },
      {
        "geometry_extrapolated": false,
        "inner_projected_radius_m": 0.06575083222301552,
        "one_blade_shaft_generalized_load_nm": -0.00019887249338147007,
        "one_tip_hinge_generalized_torque_nm": 0.0,
        "outer_projected_radius_m": 0.085,
        "role": "fixed_root",
        "source_differential_thrust_n_m": 0.28374219050081256,
        "source_differential_torque_nm_m": 0.030994455815267163,
        "source_index": 2,
        "thrust_density_measure": "whole_rotor_newton_per_projected_radial_metre",
        "torque_density_measure": "whole_rotor_newton_metre_per_projected_radial_metre",
        "whole_rotor_resisting_torque_nm": 0.0005966174801444101,
        "whole_rotor_thrust_n": 0.005461801030359236
      },
      {
        "geometry_extrapolated": false,
        "inner_projected_radius_m": 0.085,
        "one_blade_shaft_generalized_load_nm": -2.713304598810028e-05,
        "one_tip_hinge_generalized_torque_nm": -4.107266654432969e-07,
        "outer_projected_radius_m": 0.08762624833452329,
        "role": "movable_tip",
        "source_differential_thrust_n_m": 0.28374219050081256,
        "source_differential_torque_nm_m": 0.030994455815267163,
        "source_index": 2,
        "thrust_density_measure": "whole_rotor_newton_per_projected_radial_metre",
        "torque_density_measure": "whole_rotor_newton_metre_per_projected_radial_metre",
        "whole_rotor_resisting_torque_nm": 8.13991379643008e-05,
        "whole_rotor_thrust_n": 0.0007451774552367464
      },
      {
        "geometry_extrapolated": false,
        "inner_projected_radius_m": 0.08762624833452329,
        "one_blade_shaft_generalized_load_nm": -0.00019785925189349073,
        "one_tip_hinge_generalized_torque_nm": -2.6522925566658463e-05,
        "outer_projected_radius_m": 0.10950166444603104,
        "role": "movable_tip",
        "source_differential_thrust_n_m": 0.25131949251576385,
        "source_differential_torque_nm_m": 0.02713446695846921,
        "source_index": 3,
        "thrust_density_measure": "whole_rotor_newton_per_projected_radial_metre",
        "torque_density_measure": "whole_rotor_newton_metre_per_projected_radial_metre",
        "whole_rotor_resisting_torque_nm": 0.0005935777556804722,
        "whole_rotor_thrust_n": 0.005497718475715294
      }
    ],
    "logical_queries_total": 129,
    "max_hypot_sound_sqrt_enclosure_error": {
      "approx": 9.658776289286476e-15,
      "fraction": "5838372021/604462909807314587353088"
    },
    "projected_stations": [
      {
        "airfoil_id": "NACA0012",
        "chord_m": 0.024640000000000002,
        "effective_r_over_R": 0.2009101880898159,
        "effective_radius_m": 0.022000000000000002,
        "nominal_r_over_R": 0.2,
        "nominal_radius_m": 0.022000000000000002,
        "twist_rad": 0.5410520681182421
      },
      {
        "airfoil_id": "NACA0012",
        "chord_m": 0.02288,
        "effective_r_over_R": 0.4018203761796318,
        "effective_radius_m": 0.044000000000000004,
        "nominal_r_over_R": 0.4,
        "nominal_radius_m": 0.044000000000000004,
        "twist_rad": 0.4188790204786392
      },
      {
        "airfoil_id": "NACA0012",
        "chord_m": 0.02024,
        "effective_r_over_R": 0.6027305642694476,
        "effective_radius_m": 0.066,
        "nominal_r_over_R": 0.6,
        "nominal_radius_m": 0.066,
        "twist_rad": 0.29670597283903605
      },
      {
        "airfoil_id": "NACA0012",
        "chord_m": 0.01568,
        "effective_r_over_R": 0.7762439085288341,
        "effective_radius_m": 0.085,
        "nominal_r_over_R": 0.7727272727272728,
        "nominal_radius_m": 0.085,
        "twist_rad": 0.19119288624119699
      },
      {
        "airfoil_id": "NACA0012",
        "chord_m": 0.014960000000000001,
        "effective_r_over_R": 0.8030946395053741,
        "effective_radius_m": 0.08794019973352374,
        "nominal_r_over_R": 0.8,
        "nominal_radius_m": 0.08800000000000001,
        "twist_rad": 0.17453292519943295
      },
      {
        "airfoil_id": "NACA0012",
        "chord_m": 0.00704,
        "effective_r_over_R": 0.9803094639505373,
        "effective_radius_m": 0.1073455179747803,
        "nominal_r_over_R": 0.98,
        "nominal_radius_m": 0.10779999999999999,
        "twist_rad": 0.08726646259971647
      },
      {
        "airfoil_id": "NACA0012",
        "chord_m": 0.00704,
        "effective_r_over_R": 1.0,
        "effective_radius_m": 0.10950166444603104,
        "nominal_r_over_R": 1.0,
        "nominal_radius_m": 0.11,
        "twist_rad": 0.08726646259971647
      }
    ],
    "queries": [
      {
        "query": {
          "alpha_rad": -0.7583402303930604,
          "bounds": "error",
          "mach": 0.012327693187748876,
          "reynolds": 6628.817318398541
        },
        "span_clamped": false,
        "weight": 0.125
      },
      {
        "query": {
          "alpha_rad": -0.7687197499206213,
          "bounds": "error",
          "mach": 0.012327029135238265,
          "reynolds": 6628.460245691131
        },
        "span_clamped": false,
        "weight": 0.125
      },
      {
        "query": {
          "alpha_rad": -0.779099269448182,
          "bounds": "error",
          "mach": 0.012325037049247109,
          "reynolds": 6627.38906603758
        },
        "span_clamped": false,
        "weight": 0.125
      },
      {
        "query": {
          "alpha_rad": -0.7894787889757426,
          "bounds": "error",
          "mach": 0.012321717144389713,
          "reynolds": 6625.603894839775
        },
        "span_clamped": false,
        "weight": 0.125
      },
      {
        "query": {
          "alpha_rad": -0.7998583085033033,
          "bounds": "error",
          "mach": 0.012317069778330915,
          "reynolds": 6623.104924420386
        },
        "span_clamped": false,
        "weight": 0.125
      },
      {
        "query": {
          "alpha_rad": -0.7894787889757426,
          "bounds": "error",
          "mach": 0.012321717144389713,
          "reynolds": 6625.603894839775
        },
        "span_clamped": false,
        "weight": 0.125
      },
      {
        "query": {
          "alpha_rad": -0.7998583085033033,
          "bounds": "error",
          "mach": 0.012317069778330915,
          "reynolds": 6623.104924420386
        },
        "span_clamped": false,
        "weight": 0.125
      },
      {
        "query": {
          "alpha_rad": -0.7986873541551147,
          "bounds": "error",
          "mach": 0.01231766048219996,
          "reynolds": 6623.422556273931
        },
        "span_clamped": false,
        "weight": 0.125
      },
      {
        "query": {
          "alpha_rad": -0.7987043742383109,
          "bounds": "error",
          "mach": 0.012317652017145013,
          "reynolds": 6623.418004465092
        },
        "span_clamped": false,
        "weight": 0.125
      },
      {
        "query": {
          "alpha_rad": -0.7987044060822999,
          "bounds": "error",
          "mach": 0.012317652001303844,
          "reynolds": 6623.417995947017
        },
        "span_clamped": false,
        "weight": 0.125
      },
      {
        "query": {
          "alpha_rad": -0.7987044060572994,
          "bounds": "error",
          "mach": 0.01231765200131628,
          "reynolds": 6623.417995953704
        },
        "span_clamped": false,
        "weight": 0.125
      },
      {
        "query": {
          "alpha_rad": -0.7987044060822999,
          "bounds": "error",
          "mach": 0.012317652001303844,
          "reynolds": 6623.417995947017
        },
        "span_clamped": false,
        "weight": 0.125
      },
      {
        "query": {
          "alpha_rad": -0.6908823460540253,
          "bounds": "error",
          "mach": 0.01343732487155341,
          "reynolds": 6561.90258215457
        },
        "span_clamped": false,
        "weight": 0.37500000000000006
      },
      {
        "query": {
          "alpha_rad": -0.7071662117608278,
          "bounds": "error",
          "mach": 0.013435543361616814,
          "reynolds": 6561.032610284067
        },
        "span_clamped": false,
        "weight": 0.37500000000000006
      },
      {
        "query": {
          "alpha_rad": -0.7234500774676301,
          "bounds": "error",
          "mach": 0.0134301993041894,
          "reynolds": 6558.422925352926
        },
        "span_clamped": false,
        "weight": 0.37500000000000006
      },
      {
        "query": {
          "alpha_rad": -0.7397339431744326,
          "bounds": "error",
          "mach": 0.013421294116293003,
          "reynolds": 6554.074219341088
        },
        "span_clamped": false,
        "weight": 0.37500000000000006
      },
      {
        "query": {
          "alpha_rad": -0.7234500774676301,
          "bounds": "error",
          "mach": 0.0134301993041894,
          "reynolds": 6558.422925352926
        },
        "span_clamped": false,
        "weight": 0.37500000000000006
      },
      {
        "query": {
          "alpha_rad": -0.7397339431744326,
          "bounds": "error",
          "mach": 0.013421294116293003,
          "reynolds": 6554.074219341088
        },
        "span_clamped": false,
        "weight": 0.37500000000000006
      },
      {
        "query": {
          "alpha_rad": -0.7263387861953406,
          "bounds": "error",
          "mach": 0.013428879328451607,
          "reynolds": 6557.778336323115
        },
        "span_clamped": false,
        "weight": 0.37500000000000006
      },
      {
        "query": {
          "alpha_rad": -0.7263622382091967,
          "bounds": "error",
          "mach": 0.01342886815362912,
          "reynolds": 6557.772879277369
        },
        "span_clamped": false,
        "weight": 0.37500000000000006
      },
      {
        "query": {
          "alpha_rad": -0.7263622380298839,
          "bounds": "error",
          "mach": 0.013428868153714588,
          "reynolds": 6557.772879319105
        },
        "span_clamped": false,
        "weight": 0.37500000000000006
      },
      {
        "query": {
          "alpha_rad": -0.7263622380548841,
          "bounds": "error",
          "mach": 0.013428868153702672,
          "reynolds": 6557.7728793132865
        },
        "span_clamped": false,
        "weight": 0.37500000000000006
      },
      {
        "query": {
          "alpha_rad": -0.7263622380298839,
          "bounds": "error",
          "mach": 0.013428868153714588,
          "reynolds": 6557.772879319105
        },
        "span_clamped": false,
        "weight": 0.37500000000000006
      },
      {
        "query": {
          "alpha_rad": -0.6568307571861505,
          "bounds": "error",
          "mach": 0.01494675985554722,
          "reynolds": 5977.465301635404
        },
        "span_clamped": false,
        "weight": 0.625
      },
      {
        "query": {
          "alpha_rad": -0.6779750223387209,
          "bounds": "error",
          "mach": 0.014943418781711475,
          "reynolds": 5976.129148976474
        },
        "span_clamped": false,
        "weight": 0.625
      },
      {
        "query": {
          "alpha_rad": -0.699119287491291,
          "bounds": "error",
          "mach": 0.01493339705387571,
          "reynolds": 5972.121288344493
        },
        "span_clamped": false,
        "weight": 0.625
      },
      {
        "query": {
          "alpha_rad": -0.6779750223387209,
          "bounds": "error",
          "mach": 0.014943418781711475,
          "reynolds": 5976.129148976474
        },
        "span_clamped": false,
        "weight": 0.625
      },
      {
        "query": {
          "alpha_rad": -0.699119287491291,
          "bounds": "error",
          "mach": 0.01493339705387571,
          "reynolds": 5972.121288344493
        },
        "span_clamped": false,
        "weight": 0.625
      },
      {
        "query": {
          "alpha_rad": -0.6879815907117066,
          "bounds": "error",
          "mach": 0.014939508465173359,
          "reynolds": 5974.565346409837
        },
        "span_clamped": false,
        "weight": 0.625
      },
      {
        "query": {
          "alpha_rad": -0.6880232483754603,
          "bounds": "error",
          "mach": 0.014939489059371345,
          "reynolds": 5974.557585697194
        },
        "span_clamped": false,
        "weight": 0.625
      },
      {
        "query": {
          "alpha_rad": -0.6880232455173456,
          "bounds": "error",
          "mach": 0.014939489060703656,
          "reynolds": 5974.557586230008
        },
        "span_clamped": false,
        "weight": 0.625
      },
      {
        "query": {
          "alpha_rad": -0.6880232455423458,
          "bounds": "error",
          "mach": 0.014939489060692002,
          "reynolds": 5974.557586225348
        },
        "span_clamped": false,
        "weight": 0.625
      },
      {
        "query": {
          "alpha_rad": -0.6880232455173456,
          "bounds": "error",
          "mach": 0.014939489060703656,
          "reynolds": 5974.557586230008
        },
        "span_clamped": false,
        "weight": 0.625
      },
      {
        "query": {
          "alpha_rad": -0.6428167966358592,
          "bounds": "error",
          "mach": 0.016748247990714147,
          "reynolds": 4026.0291733368513
        },
        "span_clamped": false,
        "weight": 0.875
      },
      {
        "query": {
          "alpha_rad": -0.6678549856112181,
          "bounds": "error",
          "mach": 0.01674299843530239,
          "reynolds": 4024.767258463935
        },
        "span_clamped": false,
        "weight": 0.875
      },
      {
        "query": {
          "alpha_rad": -0.6928931745865771,
          "bounds": "error",
          "mach": 0.01672725305989874,
          "reynolds": 4020.982304912053
        },
        "span_clamped": false,
        "weight": 0.875
      },
      {
        "query": {
          "alpha_rad": -0.6678549856112181,
          "bounds": "error",
          "mach": 0.01674299843530239,
          "reynolds": 4024.767258463935
        },
        "span_clamped": false,
        "weight": 0.875
      },
      {
        "query": {
          "alpha_rad": -0.6928931745865771,
          "bounds": "error",
          "mach": 0.01672725305989874,
          "reynolds": 4020.982304912053
        },
        "span_clamped": false,
        "weight": 0.875
      },
      {
        "query": {
          "alpha_rad": -0.6708005457745162,
          "bounds": "error",
          "mach": 0.01674169072407472,
          "reynolds": 4024.4529041770975
        },
        "span_clamped": false,
        "weight": 0.875
      },
      {
        "query": {
          "alpha_rad": -0.6708214470661407,
          "bounds": "error",
          "mach": 0.016741680925704622,
          "reynolds": 4024.450548794977
        },
        "span_clamped": false,
        "weight": 0.875
      },
      {
        "query": {
          "alpha_rad": -0.6708214459808689,
          "bounds": "error",
          "mach": 0.01674168092621358,
          "reynolds": 4024.450548917323
        },
        "span_clamped": false,
        "weight": 0.875
      },
      {
        "query": {
          "alpha_rad": -0.670821446005869,
          "bounds": "error",
          "mach": 0.016741680926201857,
          "reynolds": 4024.450548914504
        },
        "span_clamped": false,
        "weight": 0.875
      },
      {
        "query": {
          "alpha_rad": -0.6708214459808689,
          "bounds": "error",
          "mach": 0.01674168092621358,
          "reynolds": 4024.450548917323
        },
        "span_clamped": false,
        "weight": 0.875
      }
    ],
    "query_envelopes": {
      "alpha_rad": {
        "max": -0.6428167966358592,
        "max_hex": "-0x1.491f487dbdb1fp-1",
        "min": -0.7998583085033033,
        "min_hex": "-0x1.99870738e9400p-1"
      },
      "mach": {
        "max": 0.016748247990714147,
        "max_hex": "0x1.12673e58aaa39p-6",
        "min": 0.012317069778330915,
        "min_hex": "0x1.939b11f0b39c1p-7"
      },
      "reynolds": {
        "max": 6628.817318398541,
        "max_hex": "0x1.9e4d13bc75027p+12",
        "min": 4020.982304912053,
        "min_hex": "0x1.f69f6f0ab5ff0p+11"
      }
    },
    "query_record_scope": "complete43 logical queries of baseline call;129 checked across three calls",
    "radial_cells": [
      {
        "hex": {
          "inner": "0x1.6872b020c49bbp-6",
          "midpoint": "0x1.0dd3615cf2f6cp-5",
          "outer": "0x1.676d6aa9839fap-5",
          "span_query": "0x1.3403f9ad79f49p-2"
        },
        "index": 0,
        "inner": 0.022000000000000002,
        "midpoint": 0.032937708055753884,
        "outer": 0.04387541611150776,
        "span_query": 0.3007964145785889
      },
      {
        "hex": {
          "inner": "0x1.676d6aa9839fap-5",
          "midpoint": "0x1.c10773f614488p-5",
          "outer": "0x1.0d50bea15278bp-4",
          "span_query": "0x1.004a900719451p-1"
        },
        "index": 1,
        "inner": 0.04387541611150776,
        "midpoint": 0.05481312416726164,
        "outer": 0.06575083222301552,
        "span_query": 0.5005688675561349
      },
      {
        "hex": {
          "inner": "0x1.0d50bea15278bp-4",
          "midpoint": "0x1.3a1dc3479acd2p-4",
          "outer": "0x1.66eac7ede321ap-4",
          "span_query": "0x1.66932337758fdp-1"
        },
        "index": 2,
        "inner": 0.06575083222301552,
        "midpoint": 0.0766885402787694,
        "outer": 0.08762624833452329,
        "span_query": 0.7003413205336809
      },
      {
        "hex": {
          "inner": "0x1.66eac7ede321ap-4",
          "midpoint": "0x1.93b7cc942b761p-4",
          "outer": "0x1.c084d13a73ca8p-4",
          "span_query": "0x1.ccdbb667d1daap-1"
        },
        "index": 3,
        "inner": 0.08762624833452329,
        "midpoint": 0.09856395639027717,
        "outer": 0.10950166444603104,
        "span_query": 0.900113773511227
      }
    ],
    "source_terminal_radius_m": 0.10950166444603104,
    "span_anchors": [
      0.2009101880898159,
      1.0
    ],
    "terminal_boundary_delta_m": 0.0,
    "terminal_boundary_normalized": false
  },
  "declaration_head": "33a59142f0206e1370c9a0c44116f1dd709b35d3",
  "detectability": {
    "B_abs_correct_rad_s2": {
      "approx": 1.0588342316166035e-11,
      "fraction": "330277018742138710044805342242733/31192514265229167018600948889639598935769088"
    },
    "P_scale_09_w": {
      "approx": 9.86666666666667,
      "fraction": "2453461299621615101789643618758786393194073614752718459118604242471771476939906490724093/248661618204893321077691124073410420050228075398673858720231988446579748506266687766528"
    },
    "U_P09_w": {
      "approx": 9.86666666666667e-08,
      "fraction": "7415131781344585957128017175617442073802548361202448890607370490800903369518617483841083018814309253289/75153362648762663292463379097258784876021841565066235862633311089030688803667470190838367948312598497021919232"
    },
    "hinge_gap_pass": true,
    "hinge_mutant_gap_rad_s2": {
      "approx": 91.7347827074291,
      "fraction": "100094737375743195398249543692288/1091131786892400424662493497063"
    },
    "hinge_work_pass": true,
    "hinge_work_w": {
      "approx": 8.080095669630529e-07,
      "fraction": "137475703970475070683399356064675/170141183460469231731687303715884105728"
    },
    "independent_E_dot_ref_w": {
      "approx": 4.84488720957457,
      "fraction": "1204737493553002763286103831075190525260717710825264882612373916916560635576090984869629/248661618204893321077691124073410420050228075398673858720231988446579748506266687766528"
    },
    "raw_gap_pass": true,
    "raw_mutant_gap_rad_s2": {
      "approx": 362.97299702022957,
      "fraction": "132017124944124339418214438584320/363710595630800141554164499021"
    },
    "raw_positive_bem_torque_nm": 0.0021114763792212526
  },
  "draft_sha256": "b3d3fd8e58a2476937607e04ecd2651b91cfb4c95c44ea026a39eff57dc167d6",
  "evaluations": [
    {
      "blade_count": 3,
      "hinge_radius_m": 0.085,
      "hinge_rate_aerodynamic_model": "ignored_rate_independent_quasi_steady",
      "hinge_rate_rad_s": 0.01,
      "load_mapping_model": "planar_projected_material_load_v1",
      "one_tip_hinge_generalized_load_nm": -2.693365223210176e-05,
      "projection_model": "radial_cosine_v1",
      "qualification": "screening_only_projected_rate_independent",
      "source_id": "cmm2-planar-map:0:532b27f87ff043949cdefdd0813993b01d0e4a7db349270e7f28c9797c0f7a00",
      "theta_rad": -0.2,
      "thrust_n": 0.01888616132790824,
      "whole_rotor_shaft_generalized_load_nm": -0.0021114763792212526
    },
    {
      "blade_count": 3,
      "hinge_radius_m": 0.085,
      "hinge_rate_aerodynamic_model": "ignored_rate_independent_quasi_steady",
      "hinge_rate_rad_s": 0.01,
      "load_mapping_model": "planar_projected_material_load_v1",
      "one_tip_hinge_generalized_load_nm": -2.693365223210176e-05,
      "projection_model": "radial_cosine_v1",
      "qualification": "screening_only_projected_rate_independent",
      "source_id": "cmm2-planar-map:1:ff016aa93d7d4972506f153ab58a1f8ebe153138fdbcbf78e0fb720a8b903991",
      "theta_rad": -0.2,
      "thrust_n": 0.01888616132790824,
      "whole_rotor_shaft_generalized_load_nm": -0.0021114763792212526
    },
    {
      "blade_count": 3,
      "hinge_radius_m": 0.085,
      "hinge_rate_aerodynamic_model": "ignored_rate_independent_quasi_steady",
      "hinge_rate_rad_s": 0.01,
      "load_mapping_model": "planar_projected_material_load_v1",
      "one_tip_hinge_generalized_load_nm": -2.693365223210176e-05,
      "projection_model": "radial_cosine_v1",
      "qualification": "screening_only_projected_rate_independent",
      "source_id": "cmm2-planar-map:0:532b27f87ff043949cdefdd0813993b01d0e4a7db349270e7f28c9797c0f7a00",
      "theta_rad": -0.2,
      "thrust_n": 0.01888616132790824,
      "whole_rotor_shaft_generalized_load_nm": -0.0021114763792212526
    }
  ],
  "future_v2_seal": null,
  "main_v1_preflight_seal_sha256": "389d5565d179358b4530bc98038f3046291594615d1acb0d3873655f678595b9",
  "mapped": [
    {
      "airfoil_id": "cmm2-span@fold:cmm2-0",
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
      "distributed_couple_model": "none",
      "force_basis": "e_z_and_e_t_phi",
      "geometry_extended": false,
      "hinge_radius_m": 0.085,
      "hinge_rate_aerodynamic_model": "ignored_rate_independent_quasi_steady",
      "hinge_rate_rad_s": 0.01,
      "intervals": [
        {
          "geometry_extrapolated": false,
          "inner_projected_radius_m": 0.022000000000000002,
          "one_blade_shaft_generalized_load_nm": -0.00010480760807179081,
          "one_tip_hinge_generalized_torque_nm": 0.0,
          "outer_projected_radius_m": 0.04387541611150776,
          "role": "fixed_root",
          "source_differential_thrust_n_m": 0.11536681109700814,
          "source_differential_torque_nm_m": 0.014373341408119203,
          "source_index": 0,
          "thrust_density_measure": "whole_rotor_newton_per_projected_radial_metre",
          "torque_density_measure": "whole_rotor_newton_metre_per_projected_radial_metre",
          "whole_rotor_resisting_torque_nm": 0.00031442282421537246,
          "whole_rotor_thrust_n": 0.002523696998204764
        },
        {
          "geometry_extrapolated": false,
          "inner_projected_radius_m": 0.04387541611150776,
          "one_blade_shaft_generalized_load_nm": -0.00017515306040556558,
          "one_tip_hinge_generalized_torque_nm": 0.0,
          "outer_projected_radius_m": 0.06575083222301552,
          "role": "fixed_root",
          "source_differential_thrust_n_m": 0.21292245800718473,
          "source_differential_torque_nm_m": 0.02402053421695939,
          "source_index": 1,
          "thrust_density_measure": "whole_rotor_newton_per_projected_radial_metre",
          "torque_density_measure": "whole_rotor_newton_metre_per_projected_radial_metre",
          "whole_rotor_resisting_torque_nm": 0.0005254591812166969,
          "whole_rotor_thrust_n": 0.004657767368392202
        },
        {
          "geometry_extrapolated": false,
          "inner_projected_radius_m": 0.06575083222301552,
          "one_blade_shaft_generalized_load_nm": -0.00019887249338147007,
          "one_tip_hinge_generalized_torque_nm": 0.0,
          "outer_projected_radius_m": 0.085,
          "role": "fixed_root",
          "source_differential_thrust_n_m": 0.28374219050081256,
          "source_differential_torque_nm_m": 0.030994455815267163,
          "source_index": 2,
          "thrust_density_measure": "whole_rotor_newton_per_projected_radial_metre",
          "torque_density_measure": "whole_rotor_newton_metre_per_projected_radial_metre",
          "whole_rotor_resisting_torque_nm": 0.0005966174801444101,
          "whole_rotor_thrust_n": 0.005461801030359236
        },
        {
          "geometry_extrapolated": false,
          "inner_projected_radius_m": 0.085,
          "one_blade_shaft_generalized_load_nm": -2.713304598810028e-05,
          "one_tip_hinge_generalized_torque_nm": -4.107266654432969e-07,
          "outer_projected_radius_m": 0.08762624833452329,
          "role": "movable_tip",
          "source_differential_thrust_n_m": 0.28374219050081256,
          "source_differential_torque_nm_m": 0.030994455815267163,
          "source_index": 2,
          "thrust_density_measure": "whole_rotor_newton_per_projected_radial_metre",
          "torque_density_measure": "whole_rotor_newton_metre_per_projected_radial_metre",
          "whole_rotor_resisting_torque_nm": 8.13991379643008e-05,
          "whole_rotor_thrust_n": 0.0007451774552367464
        },
        {
          "geometry_extrapolated": false,
          "inner_projected_radius_m": 0.08762624833452329,
          "one_blade_shaft_generalized_load_nm": -0.00019785925189349073,
          "one_tip_hinge_generalized_torque_nm": -2.6522925566658463e-05,
          "outer_projected_radius_m": 0.10950166444603104,
          "role": "movable_tip",
          "source_differential_thrust_n_m": 0.25131949251576385,
          "source_differential_torque_nm_m": 0.02713446695846921,
          "source_index": 3,
          "thrust_density_measure": "whole_rotor_newton_per_projected_radial_metre",
          "torque_density_measure": "whole_rotor_newton_metre_per_projected_radial_metre",
          "whole_rotor_resisting_torque_nm": 0.0005935777556804722,
          "whole_rotor_thrust_n": 0.005497718475715294
        }
      ],
      "load_mapping_model": "planar_projected_material_load_v1",
      "material_force_density_measure": "one_blade_newton_per_material_metre",
      "one_tip_hinge_generalized_torque_nm": -2.693365223210176e-05,
      "operating_condition_id": "cmm2-screen",
      "physical_qualification": false,
      "polar_schedule_id": "cmm2-span@fold:cmm2-0",
      "polar_sources": [
        "pyfoldable:first-party:c2v09-28-synthetic-polar-v1"
      ],
      "projected_tip_radius_m": 0.10950166444603104,
      "projection_factor": 0.9800665778412416,
      "projection_model": "radial_cosine_v1",
      "qualification": "screening_only_projected_rate_independent",
      "radial_domain": "station_span",
      "resisting_shaft_torque_nm": 0.0021114763792212526,
      "scenario_id": "cmm2",
      "schema_version": 1,
      "sectional_aerodynamic_couple": "excluded_in_v1",
      "source_inner_projected_radius_m": 0.022000000000000002,
      "source_outer_projected_radius_m": 0.10950166444603104,
      "source_terminal_radius_m": 0.10950166444603104,
      "source_whole_rotor_projected_thrust_n": 0.01888616132790824,
      "source_whole_rotor_resisting_torque_nm": 0.0021114763792212526,
      "synchronous_n_times_one_tip_hinge_generalized_torque_nm": -8.080095669630528e-05,
      "terminal_boundary_delta_m": 0.0,
      "terminal_boundary_normalized": false,
      "theta_rad": -0.2,
      "thrust_density_measure": "whole_rotor_newton_per_projected_radial_metre",
      "torque_density_measure": "whole_rotor_newton_metre_per_projected_radial_metre",
      "whole_rotor_aerodynamic_shaft_generalized_load_nm": -0.0021114763792212526
    }
  ],
  "margins": {
    "S_omega0": 4.2887902047863906e-05,
    "S_theta0": 2.1e-07,
    "boundaries": [
      [
        "hinge_cell_2_inner",
        0.06575083222301552
      ],
      [
        "hinge_cell_2_outer",
        0.08762624833452329
      ],
      [
        "radial_midpoint_0",
        0.032937708055753884
      ],
      [
        "radial_midpoint_1",
        0.05481312416726164
      ],
      [
        "radial_midpoint_2",
        0.0766885402787694
      ],
      [
        "radial_midpoint_3",
        0.09856395639027717
      ]
    ],
    "fold_margin_rad": 1.3707963267948966,
    "fold_pass": true,
    "partition": [
      {
        "boundary_m": 0.08762624833452329,
        "distance_m": {
          "approx": 0.0026262483345232818,
          "fraction": "189241136331863/72057594037927936"
        },
        "nearest_boundary": "hinge_cell_2_outer",
        "object": "hinge",
        "pass": true,
        "radius_m": 0.085,
        "uncertainty_m": 1.043014874852491e-09
      },
      {
        "boundary_m": 0.032937708055753884,
        "distance_m": {
          "approx": 0.010937708055753882,
          "fraction": "3152579707147549/288230376151711744"
        },
        "nearest_boundary": "radial_midpoint_0",
        "object": "mapped_interval_0_inner",
        "pass": true,
        "radius_m": 0.022000000000000002,
        "uncertainty_m": 1.043014874852491e-09
      },
      {
        "boundary_m": 0.032937708055753884,
        "distance_m": {
          "approx": 0.010937708055753878,
          "fraction": "788144926786887/72057594037927936"
        },
        "nearest_boundary": "radial_midpoint_0",
        "object": "mapped_interval_1_inner",
        "pass": true,
        "radius_m": 0.04387541611150776,
        "uncertainty_m": 1.043014874852491e-09
      },
      {
        "boundary_m": 0.06575083222301552,
        "distance_m": {
          "approx": 0.0,
          "fraction": "0"
        },
        "nearest_boundary": "hinge_cell_2_inner",
        "object": "mapped_interval_2_inner",
        "pass": false,
        "radius_m": 0.06575083222301552,
        "uncertainty_m": 1.043014874852491e-09
      },
      {
        "boundary_m": 0.08762624833452329,
        "distance_m": {
          "approx": 0.0026262483345232818,
          "fraction": "189241136331863/72057594037927936"
        },
        "nearest_boundary": "hinge_cell_2_outer",
        "object": "mapped_interval_3_inner",
        "pass": true,
        "radius_m": 0.085,
        "uncertainty_m": 1.043014874852491e-09
      },
      {
        "boundary_m": 0.08762624833452329,
        "distance_m": {
          "approx": 0.0,
          "fraction": "0"
        },
        "nearest_boundary": "hinge_cell_2_outer",
        "object": "mapped_interval_4_inner",
        "pass": false,
        "radius_m": 0.08762624833452329,
        "uncertainty_m": 1.043014874852491e-09
      },
      {
        "boundary_m": 0.032937708055753884,
        "distance_m": {
          "approx": 0.010937708055753878,
          "fraction": "788144926786887/72057594037927936"
        },
        "nearest_boundary": "radial_midpoint_0",
        "object": "mapped_interval_0_outer",
        "pass": true,
        "radius_m": 0.04387541611150776,
        "uncertainty_m": 1.043014874852491e-09
      },
      {
        "boundary_m": 0.06575083222301552,
        "distance_m": {
          "approx": 0.0,
          "fraction": "0"
        },
        "nearest_boundary": "hinge_cell_2_inner",
        "object": "mapped_interval_1_outer",
        "pass": false,
        "radius_m": 0.06575083222301552,
        "uncertainty_m": 1.043014874852491e-09
      },
      {
        "boundary_m": 0.08762624833452329,
        "distance_m": {
          "approx": 0.0026262483345232818,
          "fraction": "189241136331863/72057594037927936"
        },
        "nearest_boundary": "hinge_cell_2_outer",
        "object": "mapped_interval_2_outer",
        "pass": true,
        "radius_m": 0.085,
        "uncertainty_m": 1.043014874852491e-09
      },
      {
        "boundary_m": 0.08762624833452329,
        "distance_m": {
          "approx": 0.0,
          "fraction": "0"
        },
        "nearest_boundary": "hinge_cell_2_outer",
        "object": "mapped_interval_3_outer",
        "pass": false,
        "radius_m": 0.08762624833452329,
        "uncertainty_m": 1.043014874852491e-09
      },
      {
        "boundary_m": 0.09856395639027717,
        "distance_m": {
          "approx": 0.010937708055753878,
          "fraction": "788144926786887/72057594037927936"
        },
        "nearest_boundary": "radial_midpoint_3",
        "object": "mapped_interval_4_outer",
        "pass": true,
        "radius_m": 0.10950166444603104,
        "uncertainty_m": 1.043014874852491e-09
      }
    ],
    "partition_interpretation": "literal hinge-containing source-cell endpoints and all radial midpoints; no own-boundary exemption",
    "partition_pass": false,
    "s_tip_m": 0.024999999999999998,
    "shaft_margin_rad_s": 31.41592653589793,
    "shaft_pass": true
  },
  "motor": {
    "applied_voltage_v": 1.2000000000000002,
    "back_emf_v": 0.4,
    "current_a": 13.333333333333336,
    "electrical_power_w": 16.000000000000004,
    "line_loss_w": 1.7777777777777783,
    "shaft_power_w": 4.933333333333335,
    "torque_nm": 0.11777465788800259,
    "voltage_residual_v": 0.0,
    "winding_loss_w": 8.888888888888891
  },
  "production_acceleration": {
    "aero_collective_hinge_generalized_load_nm": -8.080095669630528e-05,
    "aero_generalized_power_w": -0.08844612375876515,
    "aero_one_tip_hinge_generalized_load_nm": -2.693365223210176e-05,
    "aero_shaft_generalized_load_nm": -0.0021114763792212526,
    "centrifugal_torque_nm": 0.0029629680823821374,
    "collective_damping_nm": -0.0,
    "collective_friction_nm": 0.0,
    "collective_hinge_actuation_nm": 0.0,
    "collective_spring_nm": -0.0,
    "damping_nm": -0.0,
    "friction_nm": 0.0,
    "mass_residual": 0.0,
    "mass_schur": 0.00010855501477493738,
    "motor_torque_nm": 0.11777465788800259,
    "omega_dot_rad_s2": 308.36298649358463,
    "rhs_hinge_nm": 0.008808103290450106,
    "rhs_shaft_nm": 0.11565893686302574,
    "shaft_gyro_nm": -4.2446457556052085e-06,
    "spring_nm": -0.0,
    "theta_ddot_rad_s2": 58.83325995823378
  },
  "q2": {
    "B_abs_correct_rad_s2": {
      "approx": 1.0588342316166035e-11,
      "fraction": "330277018742138710044805342242733/31192514265229167018600948889639598935769088"
    },
    "E_abs_rad_s2": {
      "approx": 4.4721449173629033e-13,
      "fraction": "111597955304811575486598974918353/249540114121833336148807591117116791486152704"
    },
    "M_binary64": [
      [
        0.0003697333954699034,
        2.7991697734951667e-05
      ],
      [
        2.7991697734951667e-05,
        3.0000000000000005e-06
      ]
    ],
    "M_hex": [
      [
        "0x1.83b18d77f0af7p-12",
        "0x1.d59f6d240988cp-16"
      ],
      [
        "0x1.d59f6d240988cp-16",
        "0x1.92a737110e455p-19"
      ]
    ],
    "b_binary64": [
      0.11565893686302574,
      0.008808103290450106
    ],
    "b_hex": [
      "0x1.d9bd2f7511b67p-4",
      "0x1.209fb9c9403f8p-7"
    ],
    "bound": {
      "approx": 3.53437086002806e-14,
      "fraction": "155081875490731551725977622198720021196825310799152/4387821245490359322946426145379215074833431110577691238958881795"
    },
    "branch": "relative-factor-two",
    "error": {
      "approx": 1.4502859011115278e-15,
      "fraction": "111597955304811575486598974918353/76948934840558474162544588152012240114908397568"
    },
    "inverse_norm_inf": {
      "approx": 1221270.4437758804,
      "fraction": "17323371020748665607239079773295607808/14184713229601205520612415461819"
    },
    "kappa_inf": {
      "approx": 485.72990107909675,
      "fraction": "6889939353849548745213716633149448/14184713229601205520612415461819"
    },
    "pass": true,
    "represented_residual": [
      {
        "approx": 8.66994069178435e-18,
        "fraction": "11254226454408787/1298074214633706907132624082305024"
      },
      {
        "approx": 2.6247083206279485e-19,
        "fraction": "10902611814213377/41538374868278621028243970633760768"
      }
    ],
    "rho_inf": {
      "approx": 3.6382059784419745e-17,
      "fraction": "11254226454408787/309334505003158090405999847375009"
    },
    "rows": [
      {
        "bound": 1e-08,
        "eta": 0.0,
        "pass": true,
        "residual_nm": 0.0,
        "scale_nm": 0.23131787372605148
      },
      {
        "bound": 1e-08,
        "eta": 0.0,
        "pass": true,
        "residual_nm": 0.0,
        "scale_nm": 0.017616206580900212
      }
    ],
    "x_prod_fraction": [
      {
        "approx": 308.36298649358463,
        "fraction": "5424779027606879/17592186044416"
      },
      {
        "approx": 58.83325995823378,
        "fraction": "1035005654784739/17592186044416"
      }
    ],
    "x_ref": [
      {
        "approx": 308.3629864935847,
        "fraction": "112154885488074065300050856293632/363710595630800141554164499021"
      },
      {
        "approx": 58.833259958233334,
        "fraction": "834532920870119253105405002375168/14184713229601205520612415461819"
      }
    ]
  },
  "q4": {
    "actual_bem_inputs": [
      {
        "condition": {
          "air_density_kg_m3": 1.18,
          "angular_speed_rad_s": 41.88790204786391,
          "dynamic_viscosity_pa_s": 1.79e-05,
          "forward_speed_m_s": 4.0,
          "id": "cmm2-screen",
          "pressure_pa": 100000.0,
          "temperature_k": 293.15
        },
        "non_state_call_inputs_including_metadata_sha256": "6abc0a2fbd28137fe8452ff6267bace3d9c5b675368c615ea42ff8ea935354c3",
        "schedule_id": "cmm2-span",
        "state": {
          "deployed_angle_rad": 0.0,
          "hinge_radius_m": 0.085,
          "id": "cmm2-0",
          "opening_angle_rad": -0.2
        },
        "table_metadata": [
          {
            "classification": "synthetic_test_fixture",
            "experimental_validation": false,
            "owner": "PyFoldable",
            "physical_qualification": false,
            "purpose": "C2V09-28 source-domain verification only",
            "revision": "c2v09-28-synthetic-polar-v1"
          },
          {
            "classification": "synthetic_test_fixture",
            "experimental_validation": false,
            "owner": "PyFoldable",
            "physical_qualification": false,
            "purpose": "C2V09-28 source-domain verification only",
            "revision": "c2v09-28-synthetic-polar-v1"
          },
          {
            "classification": "synthetic_test_fixture",
            "experimental_validation": false,
            "owner": "PyFoldable",
            "physical_qualification": false,
            "purpose": "C2V09-28 source-domain verification only",
            "revision": "c2v09-28-synthetic-polar-v1"
          },
          {
            "classification": "synthetic_test_fixture",
            "experimental_validation": false,
            "owner": "PyFoldable",
            "physical_qualification": false,
            "purpose": "C2V09-28 source-domain verification only",
            "revision": "c2v09-28-synthetic-polar-v1"
          },
          {
            "classification": "synthetic_test_fixture",
            "experimental_validation": false,
            "owner": "PyFoldable",
            "physical_qualification": false,
            "purpose": "C2V09-28 source-domain verification only",
            "revision": "c2v09-28-synthetic-polar-v1"
          },
          {
            "classification": "synthetic_test_fixture",
            "experimental_validation": false,
            "owner": "PyFoldable",
            "physical_qualification": false,
            "purpose": "C2V09-28 source-domain verification only",
            "revision": "c2v09-28-synthetic-polar-v1"
          },
          {
            "classification": "synthetic_test_fixture",
            "experimental_validation": false,
            "owner": "PyFoldable",
            "physical_qualification": false,
            "purpose": "C2V09-28 source-domain verification only",
            "revision": "c2v09-28-synthetic-polar-v1"
          },
          {
            "classification": "synthetic_test_fixture",
            "experimental_validation": false,
            "owner": "PyFoldable",
            "physical_qualification": false,
            "purpose": "C2V09-28 source-domain verification only",
            "revision": "c2v09-28-synthetic-polar-v1"
          }
        ]
      },
      {
        "condition": {
          "air_density_kg_m3": 1.18,
          "angular_speed_rad_s": 41.88790204786391,
          "dynamic_viscosity_pa_s": 1.79e-05,
          "forward_speed_m_s": 4.0,
          "id": "cmm2-screen",
          "pressure_pa": 100000.0,
          "temperature_k": 293.15
        },
        "non_state_call_inputs_including_metadata_sha256": "6abc0a2fbd28137fe8452ff6267bace3d9c5b675368c615ea42ff8ea935354c3",
        "schedule_id": "cmm2-span",
        "state": {
          "deployed_angle_rad": 0.0,
          "hinge_radius_m": 0.085,
          "id": "cmm2-1",
          "opening_angle_rad": -0.2
        },
        "table_metadata": [
          {
            "classification": "synthetic_test_fixture",
            "experimental_validation": false,
            "owner": "PyFoldable",
            "physical_qualification": false,
            "purpose": "C2V09-28 source-domain verification only",
            "revision": "c2v09-28-synthetic-polar-v1"
          },
          {
            "classification": "synthetic_test_fixture",
            "experimental_validation": false,
            "owner": "PyFoldable",
            "physical_qualification": false,
            "purpose": "C2V09-28 source-domain verification only",
            "revision": "c2v09-28-synthetic-polar-v1"
          },
          {
            "classification": "synthetic_test_fixture",
            "experimental_validation": false,
            "owner": "PyFoldable",
            "physical_qualification": false,
            "purpose": "C2V09-28 source-domain verification only",
            "revision": "c2v09-28-synthetic-polar-v1"
          },
          {
            "classification": "synthetic_test_fixture",
            "experimental_validation": false,
            "owner": "PyFoldable",
            "physical_qualification": false,
            "purpose": "C2V09-28 source-domain verification only",
            "revision": "c2v09-28-synthetic-polar-v1"
          },
          {
            "classification": "synthetic_test_fixture",
            "experimental_validation": false,
            "owner": "PyFoldable",
            "physical_qualification": false,
            "purpose": "C2V09-28 source-domain verification only",
            "revision": "c2v09-28-synthetic-polar-v1"
          },
          {
            "classification": "synthetic_test_fixture",
            "experimental_validation": false,
            "owner": "PyFoldable",
            "physical_qualification": false,
            "purpose": "C2V09-28 source-domain verification only",
            "revision": "c2v09-28-synthetic-polar-v1"
          },
          {
            "classification": "synthetic_test_fixture",
            "experimental_validation": false,
            "owner": "PyFoldable",
            "physical_qualification": false,
            "purpose": "C2V09-28 source-domain verification only",
            "revision": "c2v09-28-synthetic-polar-v1"
          },
          {
            "classification": "synthetic_test_fixture",
            "experimental_validation": false,
            "owner": "PyFoldable",
            "physical_qualification": false,
            "purpose": "C2V09-28 source-domain verification only",
            "revision": "c2v09-28-synthetic-polar-v1"
          }
        ]
      },
      {
        "condition": {
          "air_density_kg_m3": 1.18,
          "angular_speed_rad_s": 41.88790204786391,
          "dynamic_viscosity_pa_s": 1.79e-05,
          "forward_speed_m_s": 4.0,
          "id": "cmm2-screen",
          "pressure_pa": 100000.0,
          "temperature_k": 293.15
        },
        "non_state_call_inputs_including_metadata_sha256": "d728a22226eb1acbab7aca94f0ab4d12f52cf0411e068916e3c97a99aa9ab1ce",
        "schedule_id": "cmm2-span",
        "state": {
          "deployed_angle_rad": 0.0,
          "hinge_radius_m": 0.085,
          "id": "cmm2-0",
          "opening_angle_rad": -0.2
        },
        "table_metadata": [
          {
            "classification": "synthetic_test_fixture",
            "experimental_validation": false,
            "owner": "PyFoldable",
            "physical_qualification": false,
            "purpose": "C2V09-28 source-domain verification only",
            "q4_probe": "candidate29-q4-metadata-v1",
            "revision": "c2v09-28-synthetic-polar-v1"
          },
          {
            "classification": "synthetic_test_fixture",
            "experimental_validation": false,
            "owner": "PyFoldable",
            "physical_qualification": false,
            "purpose": "C2V09-28 source-domain verification only",
            "q4_probe": "candidate29-q4-metadata-v1",
            "revision": "c2v09-28-synthetic-polar-v1"
          },
          {
            "classification": "synthetic_test_fixture",
            "experimental_validation": false,
            "owner": "PyFoldable",
            "physical_qualification": false,
            "purpose": "C2V09-28 source-domain verification only",
            "q4_probe": "candidate29-q4-metadata-v1",
            "revision": "c2v09-28-synthetic-polar-v1"
          },
          {
            "classification": "synthetic_test_fixture",
            "experimental_validation": false,
            "owner": "PyFoldable",
            "physical_qualification": false,
            "purpose": "C2V09-28 source-domain verification only",
            "q4_probe": "candidate29-q4-metadata-v1",
            "revision": "c2v09-28-synthetic-polar-v1"
          },
          {
            "classification": "synthetic_test_fixture",
            "experimental_validation": false,
            "owner": "PyFoldable",
            "physical_qualification": false,
            "purpose": "C2V09-28 source-domain verification only",
            "q4_probe": "candidate29-q4-metadata-v1",
            "revision": "c2v09-28-synthetic-polar-v1"
          },
          {
            "classification": "synthetic_test_fixture",
            "experimental_validation": false,
            "owner": "PyFoldable",
            "physical_qualification": false,
            "purpose": "C2V09-28 source-domain verification only",
            "q4_probe": "candidate29-q4-metadata-v1",
            "revision": "c2v09-28-synthetic-polar-v1"
          },
          {
            "classification": "synthetic_test_fixture",
            "experimental_validation": false,
            "owner": "PyFoldable",
            "physical_qualification": false,
            "purpose": "C2V09-28 source-domain verification only",
            "q4_probe": "candidate29-q4-metadata-v1",
            "revision": "c2v09-28-synthetic-polar-v1"
          },
          {
            "classification": "synthetic_test_fixture",
            "experimental_validation": false,
            "owner": "PyFoldable",
            "physical_qualification": false,
            "purpose": "C2V09-28 source-domain verification only",
            "q4_probe": "candidate29-q4-metadata-v1",
            "revision": "c2v09-28-synthetic-polar-v1"
          }
        ]
      }
    ],
    "actual_mapper_inputs": [
      {
        "hinge_rate_rad_s": 0.01,
        "same_returned_bem_index": 0,
        "state_id": "cmm2-0"
      },
      {
        "hinge_rate_rad_s": 0.01,
        "same_returned_bem_index": 1,
        "state_id": "cmm2-1"
      },
      {
        "hinge_rate_rad_s": 0.01,
        "same_returned_bem_index": 2,
        "state_id": "cmm2-0"
      }
    ],
    "bit_triples_thrust_Qphi_qtheta": [
      [
        "3f9356e4d5005aa8",
        "bf614c163fd74ce0",
        "befc3df27cec3853"
      ],
      [
        "3f9356e4d5005aa8",
        "bf614c163fd74ce0",
        "befc3df27cec3853"
      ],
      [
        "3f9356e4d5005aa8",
        "bf614c163fd74ce0",
        "befc3df27cec3853"
      ]
    ],
    "finite": true,
    "index_changed_at_real_bem": true,
    "metadata_reaches_real_bem": true,
    "pass": true,
    "same_real_objects_mapped": true
  },
  "q4_variant_v1_seal_sha256": "eabbfcf107fea16b0c17d281edb167be9d49c22ffeb64e5c0618f7a865ace931",
  "raw_full_record_sha256": "3ecd1c6e70fcbe98d9047dafe56044e25dee1d5e1c695cfd5d8a13e04dc55c7c",
  "retained_observer_failures": [
    {
      "attempt": 1,
      "bem_calls": 1,
      "classification": "SCRATCH OBSERVER ERROR; not candidate rejection",
      "error": {
        "cause": "None",
        "cause_type": "NoneType",
        "message": "'FoldableBEMRotorResult' object has no attribute 'state'",
        "type": "AttributeError"
      },
      "real_mapper_calls": 0,
      "record_sha256": "4195f457f6857092561580205e41db3d5e6da0c8a119d36ebd845515c8505549",
      "script_sha256": "df1c8b54c260ffb9242e896f7d84e1d2aeab5c433d80ae230ea7620e898c6c59",
      "trajectory_calls": 0
    },
    {
      "attempt": 2,
      "bem_calls": 3,
      "classification": "SCRATCH OBSERVER ERROR; not candidate rejection",
      "error": {
        "cause": "None",
        "cause_type": "NoneType",
        "message": "'PlanarProjectedMaterialLoadResult' object has no attribute 'whole_rotor_shaft_generalized_load_nm'",
        "type": "AttributeError"
      },
      "real_mapper_calls": 3,
      "record_sha256": "0a8b1c09fb3960f8fab9f5f62959a84837c66b5272d15169b317e6dd9f757da2",
      "script_sha256": "2d987e2c48bfbcf3fe05db259241d07ee1e730cd5debc4ca1b61a750b10d5126",
      "trajectory_calls": 0
    }
  ],
  "runtime": {
    "libc": [
      "glibc",
      "2.39"
    ],
    "numpy": "2.3.5",
    "platform": "Linux-6.18.44-x86_64-with-glibc2.39",
    "python": "3.12.14",
    "scipy": "1.17.0"
  },
  "script_sha256": "3e7272a13304132245ae700d31e751b6a2afe4cdfbf1ede01df1efebb5ec9724",
  "source_call_totals_including_observer_retries": {
    "bem": 7,
    "motor": 3,
    "real_mapper": 6,
    "trajectory": 0
  },
  "source_files": {
    "pyfoldable/application/cmm2_coupled_transient_service.py": "1efbcb0ab9769063ce7e059a779abf3570aedf35c070a679cb0c2c8e9dc9f74a",
    "pyfoldable/application/coupled_transient_service.py": "5a249daf8eff06ac0a9ad36e33a74bd49292e738da5322c760ed56e5b109eade",
    "pyfoldable/application/folding_mechanism.py": "0657ff62ea98e57ed92fb91c0c00bac414c05c69a627a589a86c2ae449448859",
    "pyfoldable/application/mechanism_binding.py": "7314deffe0eecd91280cabd60dd043ca9916049f7dee542bd5fa292939e83055",
    "pyfoldable/core/airfoil.py": "3079f8cafe962556064efe74f7b9c22ceaae59bfaa5f063bb8a7ab1d2905b196",
    "pyfoldable/core/bem.py": "4ca509127e6eedb5f124bfd12ba5192c1fc2a2de87219c7a15d0e373e5d1119a",
    "pyfoldable/core/bem_rotor.py": "7df94790f8e23ca749bc2bcb741e0afbf4e93a6881f1b9b0253b4e278b326fc3",
    "pyfoldable/core/config.py": "bc55d40533c9dc634064484be83f589be8cecf5715b2d4a9f60989265764b0fe",
    "pyfoldable/core/foldable_aero_load.py": "ffc815e101ed6d9cdb24fa9581585ea03eb2b048960fadb87d4ed3a89657b6bc",
    "pyfoldable/core/foldable_rotor.py": "da2e6b694d59311463941d1551ee215c54bab24a6e92e79fd4d94713f6bb02a1",
    "pyfoldable/core/models.py": "fec0b429c5201a7e7565205df756d00d344a5d5dd94703b7775d4b74ce17b853",
    "pyfoldable/core/motor_bem_coupling.py": "9c06d9d42e90970df585b7e250981e41c497d19b9e0269a349d04e63646d670b",
    "pyfoldable/core/polar.py": "839fdb78e3ec57452d743c6bb2a997c4c2635a320bf0c181fb5efa6fc66c731d",
    "pyfoldable/core/polar_spanwise.py": "fb97b4886a1bd04cff808d940ba2dbcdaf1732ec989236ff9a2beeae8c69cfa8",
    "pyfoldable/core/rotational_augmentation.py": "8730fa755175f529ada1be7dba58b0ff1c2198e9128a448359aea1e3563f9f7a",
    "pyfoldable/core/units.py": "aee9da530eb4de2d435661a5c73c450ec60e118f995ce6379a1b7f077cbbd208",
    "pyfoldable/dynamics/cmm2_coupled_transient.py": "f120cd1ec0c329721f962abe95f16ec30fd56a1fda70f855b2991a0678736de1",
    "pyfoldable/dynamics/coupled_transient.py": "db9a73474afcd83b6874533d2efec9bbfef25f86b5350840565c0ed73afa56c0",
    "pyfoldable/dynamics/mechanism_contracts.py": "236ef2c3ec7577e49ac34747e47cb42a823574b7880cd93b7a3b0f775e19fe67",
    "pyfoldable/dynamics/mechanism_transient.py": "290cc2a928afca84a50c120e5e012019b67a8c8f53c1a3efe122a023a3efec67",
    "pythrust/propulsion/models.py": "6223b9e22087da4d450473ba7c84dd4562a94462d16084cc60026c2360f8b750"
  },
  "status": "INITIAL ONLY / NOT SELECTED / PROPOSED",
  "trajectory_calls": 0
}
```

## Initial-only scratch observing/audit recipe

```python
"""Initial-state source/preflight only. No integrator or trajectory call."""
import sys,math,json,dataclasses,hashlib,platform,struct,inspect
from pathlib import Path
from fractions import Fraction as F
import numpy,scipy
from cmm2_candidate29_declare import build,digest
import candidate29_envelope_certificate as cert
ROOT=Path(sys.argv[1]).resolve()
DECLARATION='33a59142f0206e1370c9a0c44116f1dd709b35d3'
fixture,binding,manifest,design=build(ROOT)
assert digest(manifest)=='0b37fb45c005d7a046dee6541d1a89e4a0a5cead7434621718c90d191843b7a4'
import pyfoldable.application.cmm2_coupled_transient_service as svc
import pyfoldable.core.bem as bem
import pyfoldable.core.foldable_rotor as fold
from pyfoldable.core.polar_spanwise import SpanwisePolarSection,SpanwisePolarAnchor,SpanwisePolarSchedule
from pyfoldable.core.polar import PolarFamily
from pyfoldable.dynamics.cmm2_coupled_transient import cmm2_coupled_accelerations
out={'status':'INITIAL ONLY / NOT SELECTED / PROPOSED','declaration_head':DECLARATION,'code_base':manifest['base'],'candidate_manifest_sha256':digest(manifest),'draft_sha256':binding.draft.draft_sha256,'main_v1_preflight_seal_sha256':binding.input_sha256,'future_v2_seal':None,'trajectory_calls':0,'runtime':{'python':platform.python_version(),'numpy':numpy.__version__,'scipy':scipy.__version__,'platform':platform.platform(),'libc':platform.libc_ver()},'script_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),'source_files':svc._implementation_files()}
queries=[];mathcalls=[];bems=[];maps=[];bem_inputs=[];map_inputs=[]
class MathProxy:
 def __getattr__(self,name):
  fn=getattr(math,name)
  if not callable(fn):return fn
  def call(*args):
   value=fn(*args);caller=inspect.currentframe().f_back.f_code.co_name
   if name in ('sin','cos','hypot','sqrt','atan2'):mathcalls.append({'function':name,'args':list(args),'value':value,'caller':caller})
   return value
  return call
bem.math=MathProxy()
realq=SpanwisePolarSection.query
# Section queries record emitted query dimensions and actual span interpolation weights.
def query(self,**kwargs):
 queries.append({'query':dict(kwargs),'weight':self.weight,'span_clamped':self.span_clamped})
 return realq(self,**kwargs)
SpanwisePolarSection.query=query
realbem=svc.solve_foldable_bem_rotor;realmap=svc.map_foldable_bem_aero_loads

def observed_bem(blade,state,condition,polars,**kwargs):
 bem_inputs.append({'state':dataclasses.asdict(state),'condition':dataclasses.asdict(condition),'polars':dataclasses.asdict(polars),'kwargs':{'bounds':kwargs['bounds'],'settings':dataclasses.asdict(kwargs['settings'])}})
 result=realbem(blade,state,condition,polars,**kwargs);bems.append(result);return result

def observed_map(result,**kwargs):
 map_inputs.append({'same_returned_bem_index':next(i for i,b in enumerate(bems) if b is result),'state_id':result.geometry.state.id,'hinge_rate_rad_s':kwargs['hinge_rate_rad_s']})
 result=realmap(result,**kwargs);maps.append(result);return result
svc.solve_foldable_bem_rotor=observed_bem;svc.map_foldable_bem_aero_loads=observed_map

def serial(x):
 if isinstance(x,F):return {'fraction':str(x),'approx':float(x)}
 if isinstance(x,dict):return {k:serial(v) for k,v in x.items()}
 if isinstance(x,(list,tuple)):return [serial(v) for v in x]
 return x

def norm(x):return max(map(abs,x))
def inv(M):
 a,b=M[0];c,d=M[1];det=a*d-b*c;assert det>0
 return [[d/det,-b/det],[-c/det,a/det]]
def solve(M,b):return [sum(v*x for v,x in zip(row,b)) for row in inv(M)]
def matrixnorm(M):return max(sum(map(abs,row)) for row in M)
def row_gate(M,b,x):
 rows=[]
 for row,bi in zip(M,b):
  # Frozen represented-row arithmetic; rounded row residual and scale.
  products=[float(v)*float(xi) for v,xi in zip(row,x)]
  r=(products[0]+products[1])-float(bi);scale=abs(float(bi))+sum(map(abs,products))
  eta=abs(r)/scale if scale else (0.0 if r==0 else None)
  bound=max(1e-8,64*math.ulp(scale)/scale) if scale else 0.0
  rows.append({'residual_nm':r,'scale_nm':scale,'eta':eta,'bound':bound,'pass':eta is not None and eta<=bound})
 return rows
try:
 built=svc._build_cmm2_request(binding)
 theta=-0.2;v=0.01;omega=400.0*math.pi/30.0
 motor=built.motor_evaluator(0.0,theta,v,omega);out['motor']=dataclasses.asdict(motor)
 evaluations=[built.aero_evaluator(0.0,theta,v,omega) for _ in range(2)]
 # Fixed metadata probe declared before first measurement; no physical/numeric changes.
 anchors=[]
 for a in binding.polars.anchors:
  tables=tuple(dataclasses.replace(t,metadata={**t.metadata,'q4_probe':'candidate29-q4-metadata-v1'}) for t in a.family.tables)
  anchors.append(SpanwisePolarAnchor(a.r_over_R,PolarFamily(tables)))
 schedule=SpanwisePolarSchedule(binding.polars.id,tuple(anchors))
 variant=fixture._binding(draft=binding.draft,initial_angular_velocity_rad_s=0.01,polars=schedule)
 svc.validate_cmm2_coupled_binding(variant);out['q4_variant_v1_seal_sha256']=variant.input_sha256
 probe=svc._build_cmm2_request(variant).aero_evaluator(0.0,theta,v,omega);evaluations.append(probe)
 out['evaluations']=[dataclasses.asdict(e) for e in evaluations]
 # Subject production solve only. Independent assembly below does not access production mass/Schur.
 e=evaluations[0];qphi=e.whole_rotor_shaft_generalized_load_nm;qtheta=e.one_tip_hinge_generalized_load_nm;Qm=motor.torque_nm
 prod=cmm2_coupled_accelerations(built.request.system,theta,v,omega,Qm,e,0.0)
 out['production_acceleration']=dataclasses.asdict(prod)
 N=3;m=0.01;h=0.085;c=0.01;J=m*c**2+0.0;I0=0.0001;C=m*h*c;cos=math.cos(theta);sin=math.sin(theta)
 radial=m*h**2;A=J+radial+2.0*C*cos;B=J+C*cos
 Mf=[[I0+N*A,N*B],[N*B,N*J]]
 gyro=N*C*sin*(2.0*omega*v+v**2);centrifugal=-C*omega**2*sin
 def rhs(phi,qt):return [Qm+phi+gyro,N*(0.0+qt+(-0.0*(theta-(-0.2)))+(-0.0*v)+0.0+centrifugal)]
 bf=rhs(qphi,qtheta);M=[[F(x) for x in row] for row in Mf];b=list(map(F,bf));xp=list(map(F,(prod.omega_dot_rad_s2,prod.theta_ddot_rad_s2)))
 xr=solve(M,b);res=[bi-sum(mi*xi for mi,xi in zip(row,xp)) for row,bi in zip(M,b)]
 ni=matrixnorm(inv(M));nm=matrixnorm(M);kappa=nm*ni;rho=norm(res)/(nm*norm(xp)+norm(b));Babs=ni*norm(res);Eabs=norm([a-b for a,b in zip(xp,xr)])
 rows=row_gate(M,b,xp)
 if norm(xr)==0:branch='absolute-zero';bound=Babs;error=Eabs
 elif kappa*rho<1:branch='relative-factor-two';bound=2*kappa*rho/(1-kappa*rho);error=Eabs/norm(xr)
 else:branch='inconclusive';bound=None;error=None
 out['q2']={'M_binary64':Mf,'b_binary64':bf,'M_hex':[[x.hex() for x in row] for row in Mf],'b_hex':[x.hex() for x in bf],'x_ref':xr,'x_prod_fraction':xp,'represented_residual':res,'inverse_norm_inf':ni,'kappa_inf':kappa,'rho_inf':rho,'B_abs_correct_rad_s2':Babs,'E_abs_rad_s2':Eabs,'branch':branch,'error':error,'bound':bound,'rows':rows,'pass':all(r['pass'] for r in rows) and error is not None and error<=bound}
 raw=bems[0].rotor_result.torque_nm
 gap_h=norm([a-b for a,b in zip(xr,solve(M,list(map(F,rhs(qphi,0.0)))))]);gap_raw=norm([a-b for a,b in zip(xr,solve(M,list(map(F,rhs(raw,qtheta)))))])
 # Exact independent derivative of declared mechanical energy, with emitted binary64 trig/matrix entries.
 ow,tdd=xr;fomega=F(omega);fv=F(v)
 Edot=(M[0][0]*fomega+M[0][1]*fv)*ow+(M[0][1]*fomega+M[1][1]*fv)*tdd-F(N)*F(C)*F(sin)*(fomega*fomega+fomega*fv)*fv
 Pscale=abs(Edot)+abs(F(Qm)*fomega)+abs(F(qphi)*fomega)+abs(F(N)*F(qtheta)*fv)
 # Store rounded binary64 P_scale only for its unchanged ULP component; relative contribution exact represented 1e-8.
 U=max(F(1e-8)*Pscale,F(64)*F(math.ulp(float(Pscale)))) if Pscale else F(0)
 Hpower=abs(F(N)*F(qtheta)*fv)
 out['detectability']={'raw_positive_bem_torque_nm':raw,'hinge_mutant_gap_rad_s2':gap_h,'raw_mutant_gap_rad_s2':gap_raw,'B_abs_correct_rad_s2':Babs,'hinge_gap_pass':gap_h>Babs,'raw_gap_pass':gap_raw>Babs,'independent_E_dot_ref_w':Edot,'P_scale_09_w':Pscale,'U_P09_w':U,'hinge_work_w':Hpower,'hinge_work_pass':Hpower>U}
 St=1e-8+1e-6*abs(theta);Sw=1e-6+1e-6*abs(omega);foldmargin=math.pi/2-abs(theta);shaftmargin=omega-100.0*math.pi/30.0
 geometry=bems[0].geometry;elements=bems[0].rotor_result.elements;intervals=maps[0].intervals
 hinge_cells=[x for x in elements if x.inner_radius_m<=h<=x.outer_radius_m]
 boundaries=[(f'hinge_cell_{x.index}_inner',x.inner_radius_m) for x in hinge_cells]+[(f'hinge_cell_{x.index}_outer',x.outer_radius_m) for x in hinge_cells]+[(f'radial_midpoint_{x.index}',0.5*(x.inner_radius_m+x.outer_radius_m)) for x in elements]
 objects=[('hinge',h)]+[(f'mapped_interval_{i}_inner',x.inner_projected_radius_m) for i,x in enumerate(intervals)]+[(f'mapped_interval_{i}_outer',x.outer_projected_radius_m) for i,x in enumerate(intervals)]
 stip=(geometry.effective_blade.radius_m-h)/geometry.projection_factor
 margins=[]
 for name,r in objects:
  closest=min(boundaries,key=lambda p:abs(F(r)-F(p[1])));distance=abs(F(r)-F(closest[1]));unc=abs(stip*math.sin(theta))*St+64*math.ulp(max(r,h))
  margins.append({'object':name,'radius_m':r,'nearest_boundary':closest[0],'boundary_m':closest[1],'distance_m':distance,'uncertainty_m':unc,'pass':distance>F(unc)})
 out['margins']={'S_theta0':St,'S_omega0':Sw,'fold_margin_rad':foldmargin,'shaft_margin_rad_s':shaftmargin,'fold_pass':foldmargin>St,'shaft_pass':shaftmargin>Sw,'s_tip_m':stip,'boundaries':boundaries,'partition_interpretation':'literal hinge-containing source-cell endpoints and all radial midpoints; no own-boundary exemption','partition':margins,'partition_pass':all(r['pass'] for r in margins)}
 triples=[(b.rotor_result.thrust_n,mp.whole_rotor_aerodynamic_shaft_generalized_load_nm,mp.one_tip_hinge_generalized_torque_nm) for b,mp in zip(bems,maps)]
 bits=[[struct.pack('!d',x).hex() for x in triple] for triple in triples]
 out['q4']={'actual_bem_inputs':bem_inputs,'actual_mapper_inputs':map_inputs,'bit_triples_thrust_Qphi_qtheta':bits,'finite':all(math.isfinite(x) for triple in triples for x in triple),'index_changed_at_real_bem':bem_inputs[0]['state']['id']!=bem_inputs[1]['state']['id'],'metadata_reaches_real_bem':all(t['metadata']['q4_probe']=='candidate29-q4-metadata-v1' for a in bem_inputs[2]['polars']['anchors'] for t in a['family']['tables']),'same_real_objects_mapped':len(map_inputs)==3 and [r['same_returned_bem_index'] for r in map_inputs]==[0,1,2],'pass':bits[0]==bits[1]==bits[2]}
 # Full emitted source hypotheses. Calls are observed, never replaced by assumed mathematical libm values.
 checks=[];sqrt_errors=[];trig={}
 for call in mathcalls:
  name=call['function'];args=call['args'];value=F(call['value']);caller=call['caller']
  if name=='hypot' or (name=='sqrt' and caller=='solve_bem_annulus'):
   square=sum(F(a)**2 for a in args) if name=='hypot' else F(args[0]);lo,hi=cert.sqr_bounds(square);err=max(abs(value-lo),abs(value-hi));sqrt_errors.append(err);checks.append(err<=cert.EPS)
  if caller=='evaluate' and name in ('sin','cos'):
   trig.setdefault(args[0],{})[name]=value;checks.append(0<=value<=1)
  if caller=='evaluate' and name=='atan2':checks.append(0<=value<=F(float.fromhex('0x1.921fb54442d19p+0')))
 for pair in trig.values():checks.append(set(pair)=={'sin','cos'} and pair['sin']**2+pair['cos']**2<=1+cert.EPS)
 checks.append(F(7,8)<=F(geometry.projection_factor)<=1)
 dims={key:[q['query'][key] for q in queries] for key in ('mach','reynolds','alpha_rad')}
 for key,label in [('mach','mach'),('reynolds','reynolds'),('alpha_rad','alpha')]:
  lo=F(cert.certificate[label]['lower_fraction']);hi=F(cert.certificate[label]['upper_fraction']);checks.append(all(lo<=F(x)<=hi for x in dims[key]))
 checks.append(all(0<=q['weight']<=1 and not q['span_clamped'] and q['query']['bounds']=='error' for q in queries))
 cells=[]
 for x,q in zip(elements,cert.certificate['cells']):
  vals={'inner':x.inner_radius_m,'outer':x.outer_radius_m,'midpoint':0.5*(x.inner_radius_m+x.outer_radius_m),'span_query':x.solution.r_over_R}
  for key,value in vals.items():checks.append(F(q[key]['lower_fraction'])<=F(value)<=F(q[key]['upper_fraction']))
  cells.append({'index':x.index,**vals,'hex':{k:v.hex() for k,v in vals.items()}})
 projected=fold.project_spanwise_polar_schedule(binding.polars,geometry.nominal_blade,geometry)
 checks.append(projected.anchors[-1].r_over_R==1.0 and geometry.stations[-1].effective_radius_m==geometry.effective_blade.radius_m)
 out['coverage']={'conditional_hypotheses_pass':all(checks),'check_count':len(checks),'max_hypot_sound_sqrt_enclosure_error':max(sqrt_errors),'epsilon':cert.EPS,'logical_queries_total':len(queries),'queries':queries,'query_envelopes':{k:{'min':min(vals),'max':max(vals),'min_hex':min(vals).hex(),'max_hex':max(vals).hex()} for k,vals in dims.items()},'math_observations':mathcalls,'span_anchors':[a.r_over_R for a in projected.anchors],'projected_stations':[s.as_mapping() for s in geometry.stations],'radial_cells':cells,'field_intervals':[x.as_mapping() for x in intervals],'source_terminal_radius_m':maps[0].source_terminal_radius_m,'terminal_boundary_normalized':maps[0].terminal_boundary_normalized,'terminal_boundary_delta_m':maps[0].terminal_boundary_delta_m,'effective_tip_m':geometry.effective_blade.radius_m}
 out['all_initial_requirements_pass']=all([out['q2']['pass'],out['detectability']['hinge_gap_pass'],out['detectability']['raw_gap_pass'],out['detectability']['hinge_work_pass'],out['margins']['fold_pass'],out['margins']['shaft_pass'],out['margins']['partition_pass'],out['q4']['pass'],out['coverage']['conditional_hypotheses_pass']])
except Exception as exc:
 out['failure']={'type':type(exc).__name__,'message':str(exc),'cause_type':type(exc.__cause__).__name__,'cause':str(exc.__cause__)}
finally:
 out['bem']=[b.as_mapping() for b in bems];out['mapped']=[m.as_mapping() for m in maps]
 out['actual_bem_calls']=len(bem_inputs);out['actual_mapper_calls']=len(map_inputs)
 Path('/tmp/candidate29_initial_preflight.json').write_text(json.dumps(serial(out),sort_keys=True,indent=2,allow_nan=False)+'\n')
 print(json.dumps(serial({k:v for k,v in out.items() if k not in ('bem','mapped','q4','coverage','source_files')}),sort_keys=True,indent=2))
```

## Pure captured-data audit recipe

```python
"""Pure audit of already captured initial data; zero source calls."""
from pathlib import Path
from fractions import Fraction as F
import json,hashlib,subprocess,math,bisect
root=Path('/workspace/scratch/489b86ee3206/cmm2-feasibility-proposal')
x=json.load(open('/tmp/candidate29_initial_preflight.json'));c=x['coverage'];rows=[]
for cell in c['radial_cells']:
 ratio=cell['span_query'];stations=c['projected_stations'];coords=[s['effective_r_over_R'] for s in stations];j=bisect.bisect_right(coords,ratio);lo,hi=stations[j-1:j+1]
 w=(ratio-lo['effective_r_over_R'])/(hi['effective_r_over_R']-lo['effective_r_over_R']);chord=lo['chord_m']+w*(hi['chord_m']-lo['chord_m']);twist=lo['twist_rad']+w*(hi['twist_rad']-lo['twist_rad'])
 sol=x['bem'][0]['rotor_result']['elements'][cell['index']]['solution']
 radius=ratio*c['effective_tip_m']
 rows.append({'cell':cell['index'],'lower_station':j-1,'upper_station':j,'weight':w,'weight_hex':w.hex(),'chord_m':chord,'chord_hex':chord.hex(),'twist_rad':twist,'twist_hex':twist.hex(),'recomputed_annulus_radius_m':radius,'pass':0<=w<=1 and chord==sol['chord_m'] and twist==sol['twist_rad'] and radius==sol['radius_m']})
assert all(r['pass'] for r in rows)
source=[]
for path,hashval in x['source_files'].items():
 # implementation manifest may be path->sha mapping, inspected below
 data=subprocess.check_output(['git','show',x['code_base']+':'+path],cwd=root)
 assert hashlib.sha256(data).hexdigest()==hashval,(path,hashval)
 source.append(path)
result={'source_calls':0,'trajectory_calls':0,'captured_file_sha256':hashlib.sha256(Path('/tmp/candidate29_initial_preflight.json').read_bytes()).hexdigest(),'interpolation_rows':rows,'source_files_equal_base':source,'all_pass':True}
Path('/tmp/candidate29_captured_audit.json').write_text(json.dumps(result,sort_keys=True,indent=2)+'\n');print(json.dumps(result,indent=2))
```

A subsequent [prospective partition-policy declaration](cmm2_c2v09_partition_policy_proposal.md)
uses unchanged candidate29 and a whole stored-scale angle neighborhood. It
preserves literal v1 FAIL/raw zeros and every historical capture; no structural
alias is relabelled as passing v1. The separately versioned proposal and Q4
successor conjunction are **PROPOSED / NOT FROZEN / NOT IMPLEMENTED**.
Committed-declaration review precedes any new initial-only assessment; no
trajectory, ordered selection, v2 seal or acceptance is authorized.
