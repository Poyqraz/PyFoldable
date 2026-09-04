# PY-05 — software completion and PR #53 corrections

## Completion boundary

PY-05A/B implements the prescribed-drive planar rigid-tip software workflow:
signed RPM/hinge-torque histories, finite SI mass/CG/hinge inertia, optional
explicit regularized kinetic friction, terminal first contact, source-bound
reports, active-draft mass binding and two explicit-run UI paths. It does not
claim a validated passive deployment mechanism or a fully coupled rotor model.
Every result remains `physical_qualification=false`.

Still outside this boundary are measured PA-CF mass/friction calibration, static
stiction/breakaway, contact reaction/impact/restitution/latching, arbitrary hinge
axes, aerodynamic feedback and motor/BEM transients. Those require separate
models and evidence, not hidden defaults. PY-06 is next for calibration,
uncertainty and comparison infrastructure. PR #3 remains separate. The 250/140 mm
envelope conflict and PR-06C/09/10 gates are unchanged. Print orientation remains
outside scope.

## Numerical corrections

* Checking only accepted-step endpoints misses an out-and-back stop excursion.
  Each public RK45 dense interpolant is quartic. Five evaluations reconstruct it
  over normalized time [0,1]; derivative roots divide it into monotone intervals,
  and every stop is searched on every interval. The earliest contact terminates
  the run with its pre-impact state. Numerically ambiguous near-tangencies fail
  closed instead of becoming successful no-contact runs.
* Coarse absolute time origins are rejected with a request to rebase to elapsed
  seconds. Timestamp precision must not change the reported impact velocity.
* `J >= m*c*c` admits only scale-relative floating-point roundoff. Nonfinite
  derived quantities and arithmetic exceptions are rejected; no partial result
  is published as success.
* RPM is signed and supports reversal. Angle and angular-velocity absolute
  tolerances are explicit. Knot samples use the right-side drive derivative,
  except a terminal contact found at a knot belongs to its terminating segment.
* A conservative full-history sample preflight plus per-step sample and RHS
  evaluation limits bounds work. A possible early contact does not waive it.
* Failed, invalid or changed UI requests remove stale results and downloads.
  Stops, spring rest angle, initial velocity and torque endpoints are visible.

The numerical implementation uses public [SciPy 1.7.1 RK45](https://docs.scipy.org/doc/scipy-1.7.1/reference/reference/generated/scipy.integrate.RK45.html)
and [dense output](https://docs.scipy.org/doc/scipy-1.7.1/reference/reference/generated/scipy.integrate.RK45.dense_output.html)
APIs, not private coefficient attributes. This finds first contact in the
numerical interpolant; it does not certify the exact ODE or physical hardware.

## Active-draft mass binding

`bind_mechanism_draft` rehashes and reparses the exact `DesignDraftArtifact` TOML.
Only a +z planar hinge, zero offsets, radial open orientation and zero deployed
stop are supported. The draft supplies hinge geometry/stops, profile identity and
the envelope audit. It supplies neither guessed mass nor an implicit transient
RPM. The modeled body is one tip, not all blades.

The caller supplies immutable radial mass or quadrature samples, each with mass,
CG distance `x_i` along the tip, source and optional intrinsic +z inertia:

`m=sum(m_i); c=sum(m_i*x_i)/m; J_hinge=sum(m_i*x_i*x_i+I_i)`.

Every sample CG must lie inside the active tip. This does not certify each lump's
shape, thickness, density, strength or collision clearance. A quadrature rule can
represent an explicitly assumed distribution but is not a PA-CF measurement.

`DryFriction` accepts only explicit `none` or `regularized_coulomb`:
`Q_f=-tau_c*tanh(theta_dot/v_transition)`. The coefficients and source are
required and dissipated power is reported. The smooth law has zero torque at zero
velocity, so it cannot model static holding or breakaway. No literature value is
silently transferred to the prototype.

Binding validation rebuilds all derived fields before use. Reports retain exact
draft TOML, source/profile identities, complete supplied mass samples, normalized
mechanical and drive inputs, binding hash, source/runtime identities and solver
samples. Hashes identify content; they do not authenticate its source.

## UI and strict JSON

The independent **Mekanizma Geçişi** page accepts signed endpoints or a strict
piecewise drive JSON and optional explicitly sourced friction. It is not bound to
the active design. **Tasarım Geometrisi → Aktif taslağa bağlı mekanizma analizini
aç** uses the current draft plus explicit mass/mechanical JSON. Empty input never
runs, and any draft/input change invalidates the old result.

Drive JSON permits exactly `time_s`, `rpm`, and
`applied_hinge_torque_nm`; duplicates, nonfinite constants, unknown fields and
inputs over 64 KiB are rejected. Bound JSON is limited to 256 KiB and 4096 mass
samples. Contact policy is terminal first contact, not impact response.

This example is a synthetic software fixture, not recommended prototype data:

```json
{
  "mass_distribution": {"source": "synthetic, not measured", "classification": "synthetic_test_fixture",
    "samples": [{"distance_from_hinge_m": 0.01, "mass_kg": 0.04,
                 "source": "synthetic point", "intrinsic_inertia": 0.0}]},
  "mechanical_source": "explicit synthetic assumptions; not calibration",
  "spring_stiffness_nm_rad": 0.02,
  "rest_angle_rad": 0.0,
  "viscous_damping_nm_s_rad": 0.001,
  "initial_angle_rad": -0.5,
  "initial_angular_velocity_rad_s": 0.0,
  "drive": {"time_s": [0.0, 0.05, 0.1], "rpm": [0.0, 60.0, -60.0],
            "applied_hinge_torque_nm": [0.0, 0.0, 0.0]},
  "dry_friction": {"mode": "none", "coulomb_torque_nm": 0.0,
                   "transition_velocity_rad_s": 0.0,
                   "source": "explicit_frictionless_model"}
}
```

## Verification contract

Regression tests cover hidden lower/upper excursions, tangency ambiguity,
noncontact, time resolution, signed-drive invariants, inertia scaling, overflow,
friction analytic decay, JSON errors/hashes, mass quadrature, unsupported
topology, stale UI state and controlled failure. Tests use `unittest.TestCase`
where practical and remain pytest-compatible. Local NumPy/SciPy unittest and
compile checks do not replace the complete GitHub Python 3.10/3.11 test matrix or
real Streamlit `AppTest`. Independent review and exact tested-head CI are required
before merge; CI cannot establish physical qualification.
