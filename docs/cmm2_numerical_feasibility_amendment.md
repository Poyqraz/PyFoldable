# CMM-2 numerical-feasibility amendment proposal

Status: **REVIEWED / FROZEN FOR IMPLEMENTATION — CMM-2 NUMERICAL FEASIBILITY AMENDMENT**.

Implementation status: **NOT IMPLEMENTED / NOT AUTHORIZED BY THIS DESIGN FREEZE**.

Current cumulative implementation authority is [section 7](#7-cumulative-implementation-authority-and-live-eligibility).
Earlier proposal statuses, acceptance prerequisites and measured dispositions
below retain their declaration-time scope; the cumulative status record in
section 8 records conditional design freeze separately from implementation.

Proposal base: `4cf0d0ea017fa824ba8d4a063ceddd015dae09d6`.
This document proposes two separately reviewable amendments; it changes no
existing normative section. The [frozen Radau contract](cmm2_radau_remediation_contract.md)
and [frozen PR-C contract](cmm2_numerical_verification_contract.md) remain in
force. Approval to publish this proposal is not contract freeze or implementation
authorization. Candidate28 below retains its unresolved mapper-coverage blocker; candidate29
is separately declared in the [append-only proposal](cmm2_c2v09_candidate29_proposal.md);
**it is not a selectable or freeze-ready fixture**.

Main at this base ships CMM-2 RK45 / numerical implementation v1. Draft PR
[#84](https://github.com/Poyqraz/PyFoldable/pull/84) contains an unmerged
Radau / v2 attempt. Its starting head was
`e623971c61a3c8a1f770ab37a8f5841f254a5428`; the evidence inspected here is
later CI head `8978acecbd7eabf89a1ead92e90141062081358c`. During this review
PR #84 advanced to `be6b85d5fe693528ddc333ec1d7533dcf2ffd075`, publishing
the certificate/rejection records linked below; it remains Draft/BLOCKED.
Draft PR [#81](https://github.com/Poyqraz/PyFoldable/pull/81) remains unchanged
and BLOCKED at `1fdf213bb991b2f155bf812d837bb4dcb73a8cc8`. Neither branch's
commits enter this proposal. No trajectory of the proposed candidate was run.

Independent CMM-2 numerical verification is NOT ESTABLISHED. ADR-009 is
NOT CREATED / NOT ACCEPTED. `physical_qualification=false`; PR-06C remains
unresolved; GEOM promotion, calibration and experimental validation are NONE.
Model, load-map, qualification and source-bound identities do not change.
The original technical head `613072514f793f2a1bc65704f9158f536210707f`, amended
head `b840ec55b4d1dd57197b97e91e1a48a7fbe7da0d`, and frozen Radau technical
head `2ec4da9acdccc7508fab7c33f289ec9771b2ea65` retain their historical scope.

## 1. Evidence and limits

### 1.1 Direct CI C2V-07 certificate

The Python 3.10 job [110107684678](https://github.com/Poyqraz/PyFoldable/actions/runs/36780035746/job/110107684678)
of PR #84 run `36780035746` contains the following complete
`C2V07_CERTIFICATE` plus the root bracket in its traceback. Runtime: Python
3.10, NumPy 2.2.6, SciPy 1.15.3. This is directly retrieved CI evidence,
not a local reproduction on SciPy 1.17.0. The same PR run's Python 3.11 /
SciPy 1.17.1 job succeeded; the push run `36780030753` succeeded on both.
A green run does not supersede this captured failure on the same head.

```python
start = 0.7492500000000007
end = 0.7512500000000008
origin = 0.0
last_published = start
T_old_hex = "0x1.7f9db22d0e567p-1"
H_hex = "0x1.0624dd2f1aa00p-9"
dense_t_hex = "0x1.80a3d70a3d711p-1"
y_old_hex = (
    "-0x1.ffb15b573f0f0p-2",
    "-0x1.9999999999f5dp-2",
    "0x1.3fffffffffdecp+5",
)
Q_hex = (
    ("-0x1.a36e2eb1c491ap-11", "0x1.0f6da2e25f3cfp-61", "-0x1.78492e8ed0618p-60"),
    ("0x1.938f7125ea0e2p-52", "-0x1.f3e51736ddedap-49", "0x1.d93b07ad3e3d8p-50"),
    ("0x1.84097c574dba7p-50", "0x1.abb3e591b4468p-51", "-0x1.9256b94c1c678p-52"),
)
# Exact captured enclosure and Brent anchor, in normalized coordinates:
l = Fraction(52776558117645, 140737488355328)
r = Fraction(26388279058823, 70368744177664)
anchor = l
```

Decode every hexadecimal coefficient with `float.fromhex`, then
`Fraction.from_float`. The represented cubic is
`y(x)=y_old+Q[:,0]*x+Q[:,1]*x**2+Q[:,2]*x**3`; **no extra H multiplies Q**.
For the lower-stop polynomial `P(x)=theta(x)-Fraction.from_float(-0.5)`,
exact arithmetic gives `P(l)>0`, `P(r)<0`, and
`Q[0,0]+2*abs(Q[0,1])+3*abs(Q[0,2])<0`. Thus it is strictly decreasing on
`[0,1]` and the bracket contains exactly one stop root. Its width is
`2**-47 = 7.105427357601002e-15`.

Here `T_old=6748644041614695/9007199254740992` and
`H=9007199254741/4503599627370496`. The neighboring binary64 timestamps are
`0x1.7fffffffff839p-1` and `0x1.7fffffffff83ap-1`.

| Timestamp | Normalized coordinate | Minimum distance from captured I | Frozen normalized conversion allowance at timestamp |
| --- | --- | --- | --- |
| Lower | `3377699719529/9007199254741` | `3.1419311596793436e-14` | `1.3749999998891025e-14` |
| Upper | `6755399439059/18014398509482` | `1.6986412276863342e-14` | `1.3749999998891581e-14` |

The upper minimum distance is exactly
`10766417859245/633825300114115263698305024`; its allowance, treating decimal
`1e-14` as the stated rational policy constant, is
`24769797948541/1801439850948200000000000000`.
The strict gap is about `3.2364122779717614e-15` normalized units. Using the
stored binary64 `1e-14` instead preserves the strict inequality. Both times
are inside the accepted step and advance past `last_published`. Exact dense
hinge rates at both are approximately `-0.4000000000000822 rad/s`, satisfying
the lower-stop direction rule. With origin zero, publication adds no rounding.
The original CI exception text is `CMM-2 contact direction is unresolved.`; that generic
label must not be treated as proof of a direction defect. The certified
conversion allowance is the obstruction for this captured polynomial.

The earlier source-derived conservative proof used `anchor +/- 1e-14`, not
this captured bracket. It gives upper-neighbor minimum distance
`1.4091839634464344e-14`, maximum allowance `1.3749999998891440e-14`, gap
`3.4183963557290413e-16`. Those are independently derived numbers, not raw CI
measurements. The actual captured bracket above establishes the stronger
one-step obstruction without assuming that envelope is the CI bracket.

Bounded refinement can repair an unnecessarily unresolved identity, direction,
or threshold decision when enough precision is available. It cannot move this
represented root or add a binary64 time inside its existing conversion
allowance: every sub-enclosure of this I retains the strict separation from
both nearest neighbors, and farther timestamps are farther away. Changing
step placement to fit the fixture, suppressing the exception or fitting a
new tolerance is not a repair permitted by the frozen policy. This is a
statement about one captured accepted step, not all possible Radau implementations.

The subsequently committed [certificate replay](https://github.com/Poyqraz/PyFoldable/blob/be6b85d5fe693528ddc333ec1d7533dcf2ffd075/reports/c2v07_representability/certificate.json)
contains the identical t/y_old/Q values and classifies the failure as
`conversion_infeasible`. It records the prior push and PR-merge checkouts
as sharing tree `07ff58200f6db56e3db5299dde07cb6fb23e1eee`; the earlier
pass/fail variation is therefore not explained by a source-tree difference.
This is later captured replay provenance, distinct from the original CI line.

### 1.2 Existing ordered C2V-09 source-rejection evidence

PR #84's recorded walk at `8978ace...` constructed 00 through 27 in order,
selected none, and reported record SHA-256
`1c465dae2d835fc85f468636131a2af6bce90220bcbde71c03ebea69c4ad3cf9`.
This digest and dispositions are reported in its PR body. The reviewed test
`tests/dynamics/test_cmm2_c2v09_preflight.py` calls the real motor, BEM and
mapper, writes `/opt/cursor/artifacts/c2v09_preflight.json`, and asserts 28 recorded rows, the first-row source rejection, no selected
candidate and BLOCKED status. It does not assert each row disposition. That earlier JSON was not uploaded as a GitHub Actions artifact.
Its historical digest is preserved, not retroactively recomputed.

PR #84 later committed the [complete source-rejection record](https://github.com/Poyqraz/PyFoldable/blob/be6b85d5fe693528ddc333ec1d7533dcf2ffd075/reports/c2v09_ordered_preflight/selection_record.json)
at `be6b85d...`. Its `canonical` object was retrieved and independently hashed
using sorted compact JSON in the record's own format (not the proposed
float-hex manifest format). SHA-256 is
`457186d5f52a40099acbebfe0e8ffc47eb2a8ee5fd43605ee159ae9c76cd1579`.
Every one of its 28 rows was checked for ordered ID 00…27 and SOURCE DOMAIN
disposition; selected_index and selected_input_sha256 are null, status is
CONTRACT BLOCKED, and trajectory_metrics_computed is false. Its historical
critical manifest ID is `prc_critical_fixture_manifest_v1`, reported manifest
digest `ca64ca282261702b81b6b2e5730ebb95d7db9ea39041d8d83a3d948223195090`.
That historical manifest digest is provenance from the record, not a new
recomputation of its executable fixture. This is a verified rejection record,
not completed all-predicate successful preflight: Q2/Q4/detectability/domain
and partition metrics explicitly remain unmeasured.

| Candidates | Captured source-record first rejection |
| --- | --- |
| 00–08, 10–12, 14–21, 23, 25 | Mach about 0.012317 outside `[0,0]` |
| 09 | Mach about 0.0151031 outside `[0,0]` |
| 13 | Mach about 0.0121835 outside `[0,0]` |
| 22 | Mach about 0.012318 outside `[0,0]` |
| 24 | Mach about 0.0126748 outside `[0,0]` |
| 26 | Motoring domain |
| 27 | Current limit |

Mechanics, inertia provenance, motor, battery, environment, loads, state or
controls vary as specified in frozen PR-C section 11. None widens the old
Mach support `[0,0]`, Reynolds support `[100000,100000]`, or alpha support
`[-0.5,0.5]`; CL/source/metadata changes do not change support. Source-valid
BEM therefore cannot be inferred by fixing the observed Mach query alone.
Q4 was not reached; detectability, partition and trajectory metrics were
unmeasured. The earlier walk stopped as PREFLIGHT INCOMPLETE if a mapped load
was reached; the later source-rejection record explicitly records no selection.
Neither record proves the remaining predicates were implemented. The complete
selector specified below remains future work.

## 2. Proposed timestamp policy — not current frozen policy

Proposed identity: `cmm2_contact_timestamp_quantization_v1_proposed`.
This replaces only conversion accounting and the explicit timestamp choice;
root isolation/refinement accuracy and all state/contact/domain gates remain.
The current frozen policy requires converted coordinates to remain inside its
root allowance without an explicit quantization contribution. The proposed
policy separates root-location uncertainty from binary64 representation.

### 2.1 Certified root and exact accounting

Let `I=[l,r]` identify one root `xi_root`, with `H>0`. All endpoints,
coefficients, stored binary64 `dense.t_old`, `dense.h`, and origin are converted
**directly** with `Fraction.from_float`. Normalize audit endpoints by exact
rational subtraction/division; no decimal reconstruction, inward rounding or
clamping. Preserve the existing isolation width/accuracy, recursion limit 32,
refinement limit 80 and shared work ceilings. The 80 refinements and the
`2**-80` width criterion are separate limits, not a recursion depth of 80.

Choose z before examining timestamp eligibility: the exact singleton if
proven; otherwise the retained certified Brent anchor if it lies in the
current I; otherwise the exact rational midpoint. Refinement retains root
identity. Recompute z by that same rule; do not search representatives or
accepted steps for a favorable timestamp. Define, using exact rational arithmetic:

```text
D = max(abs(l-z), abs(r-z))
p = T_old + H*z
R = Fraction.from_float(t_relative)
P = Fraction.from_float(t_public)
a = origin + R
Q_r = abs(R - p)
Q_p = abs(P - a)
```

Here `Fraction(t_relative)` and `Fraction(t_public)` mean
`Fraction.from_float` of the actual stored binary64 times. Q_r and Q_p are
nonnegative seconds. For every identified root in I, the triangle inequality
proves

```text
abs(Fraction(t_public) - (origin + T_old + H*xi_root))
 <= H*abs(z-xi_root) + Q_r + Q_p
 <= H*D + Q_r + Q_p.
```

Require `H*D <= U_root_time`, with the **unchanged frozen U_root_time
contribution** and its existing C2V-07 formula/arguments. Compute and record
those original step-width and xi_event arguments; do not replace step_width
by a favorable value of H or re-fit 1e-14. When checking the rational bound,
convert the original computed finite binary64 allowance directly to Fraction.
Q_r is the entire chosen timestamp displacement; there is no extra selection
ULP term. Q_p is only publication rounding of `origin+t_relative`, not rounding
of `origin+p`. Thus neither displacement is counted twice.

### 2.2 Frozen permitted selection set and order, if accepted later

A nearest-only rule would be stricter about direction. It is **not** this
proposal. Use exactly the two finite adjacent binary64 values bracketing p:
`f_down <= p <= f_up`, with `nextafter(f_down,+inf)==f_up` when p is not
representable. If p is exactly representable, the set is that singleton;
no unrelated neighbor is added. Selection order is nearest, ties to even,
then the other bracketing neighbor. This is a bounded directed option, not
an arbitrary +/-8-ULP search and not a claim that the second choice is nearest.

Derive each neighbor and its exact rounding cell from adjacent float values,
midpoints and significand parity, including exponent boundaries, subnormals
and ties. Prove nearest-even membership. For the non-nearest option prove it
is the other immediate enclosure neighbor. Its exact displacement is < the
adjacent gap for an interior p; nearest displacement is <= half that gap.
Record actual cell endpoints, tie ownership, selected option and Q_r. Each
option publishes `t_public=RN64(origin+Fraction(t_relative))`, with correctly
rounded nearest-even addition, and separately certifies that public rounding
cell and Q_p. No intermediate decimal or double-rounded conversion is allowed.
Overflow, unavailable finite neighbors or uncertified cells fail closed.

For each option certify **both** converted relative coordinates

```text
x_relative = (Fraction(t_relative)-T_old)/H
x_public = (Fraction(t_public)-origin-T_old)/H.
```

Both must satisfy exact accepted-interval membership and the unchanged
contact direction, pre-snap angle and state rules. The selected time need
not lie inside I: that displacement is precisely what Q_r/Q_p describe.
Instead certify its association to the already identified root: no intervening
contact candidate, no root-identity ambiguity, unchanged earliest eligible
root order, and no crossing of an earlier event/domain boundary. Distinct
root candidates with colliding published timestamps are rejected even if their
relative timestamps differ. Enclosures whose order cannot be proven must be
refined within the existing shared work limits or fail.

Only a **proven ineligible** option permits trying the next option. A predicate
that remains unresolved after bounded refinement fails the entire conversion;
it is not skipped to favor the other timestamp. Advancement must hold in
relative and public coordinates. Publication collision, unresolved direction,
identity/order, interval equality handling, state or domain decision remains
failure. Nearest-first selection does not claim universal feasibility.

The existing exact-1/3 direction witness illustrates the necessary choice:

| Choice | Relative hex | Public hex | Dense rate minus direction threshold |
| --- | --- | --- | --- |
| Nearest | `0x1.5555555555555p-2` | `0x1.aaaaaaaaaaaaap-1` | `+2**-54` relative; `+2**-52` public: fails |
| Upper neighbor | `0x1.5555555555556p-2` | `0x1.aaaaaaaaaaaabp-1` | `-2**-53`: passes |

For this witness, signed relative/public displacements for nearest are
`-1/54043195528445952` and `-1/18014398509481984`; for upper they are
`+1/27021597764222976` and zero. Q_r/Q_p use their absolute values. This
witness comes from PR #84's conversion regression, not the real C2V-07 step.
The upper choice must remain eligible under the proposed rules; a nearest-only
implementation would not conform to this proposal.

Whenever refinement changes z or p, **regenerate and certify the neighboring
pair and restart nearest-first classification**. Previous eligibility,
ineligibility or rounding-cell evidence cannot authorize the new pair. Retain
the identified root and shared work counters; do not reset refinement/root
budgets or skip an unresolved decision. Re-establish both coordinate predicates,
actual public-time domain audit, identity/order/direction and state gates for
the new pair; `H*D <=` unchanged U_root_time remains required.

### 2.3 Proposed C2V-07 arithmetic and audit extent

Before: frozen Radau section 7 and PR-C C2V-07 use

```text
T_allow_frozen = (S_theta_event + 4*angle_tol_contact)/v_min + U_root_time
abs(t_contact - t_c) <= T_allow_frozen
```

After, **only if this policy is independently reviewed and frozen**:

```text
require H*D <= U_root_time
T_allow_proposed = T_allow_frozen + Q_r + Q_p
abs(Fraction(t_public) - Fraction(t_c)) <= T_allow_proposed
```

Use exact rational differences and outward certified arithmetic for decisions;
no inward-rounded threshold. Root error H*D is already covered by U_root_time,
so do not add it again. The unchanged angle/state tolerances, five observation
nodes, terminal pre-impact rate/speed gates, v_min, root isolation accuracy,
controls and `max e_j <= 1` all still apply. Observe the original cubic before
snap at the actual relative contact time and at the exact public-relative
coordinate; compare the analytic target in the same declared origin. Published
stop snapping cannot substitute for either dense observation. This is a
returned-time representation bound, not a new root-location tolerance, tangent
timing allowance or physical error theorem.

Audit the complete accepted interval from its exact start through at least
`max(Fraction(t_relative), Fraction(t_public)-origin)` and any retained contact
enclosure extent required by the existing identity proof. Audit every endpoint
and stationary value with represented coefficients. The actual public event
coordinate must be included; auditing only the internal time is insufficient.
No success can hide an intervening fold/shaft exit or mechanical-stop breach.
No sampling fallback or reset work budget is introduced.

For large origins, Q_p can dominate the local root error. That does not grant
permission to move an event outside its accepted interval, collapse events,
lose advancement, or loosen state gates. Such cases fail closed even though
the triangle inequality itself remains true. There is no unbounded search for
a favorable neighboring public time. A successful returned time requires all
certificates; this proposal does not assert PR #84 now passes.

## 3. Proposed C2V-09 v2 candidate manifest

Proposed selector identity: `prc_c2v09_ordered_candidates_v2_proposed`.
Keep 00…27, their order, literals, seals and historical v1 manifest unchanged.
Append only `C2V09-28` derived from 23; replace only its polar source. The
new manifest has a new digest and retains the old contract/manifest identity
as provenance rather than retroactively assigning a new hash to old evidence.
After future freeze, drop `_proposed` only by an explicit reviewed status
change; no current selector consumes this document.

### 3.1 Executable synthetic polar definition

The coefficients are a priori constants matching candidate23's CL/CD/CM;
no trajectory result selected or fitted them. These are first-party synthetic
verification data, not NACA0012 measured performance. The airfoil/scenario and
schedule IDs remain the same to isolate the source change. Every table carries
explicit synthetic provenance; real-source claims are prohibited.

```python
from pyfoldable.core.models import PolarTable
from pyfoldable.core.polar import PolarFamily
from pyfoldable.core.polar_spanwise import SpanwisePolarAnchor, SpanwisePolarSchedule

META = {
    "classification": "synthetic_test_fixture",
    "owner": "PyFoldable",
    "purpose": "C2V09-28 source-domain verification only",
    "revision": "c2v09-28-synthetic-polar-v1",
    "physical_qualification": False,
    "experimental_validation": False,
}
ALPHA = (-float.fromhex("0x1.921fb54442d19p+1"), 0.0,
          float.fromhex("0x1.921fb54442d19p+1"))
TABLES = tuple(
    PolarTable(
        airfoil_id="NACA0012", scenario_id="cmm2", reynolds=re, mach=ma,
        alpha_rad=ALPHA, cl=(0.6,)*3, cd=(0.02,)*3, cm=(0.0,)*3,
        source="pyfoldable:first-party:c2v09-28-synthetic-polar-v1",
        metadata=dict(META),
    )
    for ma in (0.0, 0.2) for re in (1.0, 1.0e6)
)
FAMILY = PolarFamily(TABLES)
SCHEDULE = SpanwisePolarSchedule("cmm2-span", (
    SpanwisePolarAnchor(0.2, FAMILY), SpanwisePolarAnchor(1.0, FAMILY),
))
```

Mach-major / Reynolds-minor table order is fixed. Alpha endpoints are
`+/-3.1415926535897936 rad`, outward of mathematical pi. Mach and Reynolds
are dimensionless; CL/CD/CM are dimensionless. Alpha and Mach interpolation
are the repository's linear interpolation; Reynolds is log-linear; spanwise
interpolation is unchanged. Bounds remain `error`, with the repository's
existing endpoint handling, no extrapolation or clamp. Constant endpoint
coefficients do not assert bit-identical interpolated coefficients: actual
floating-point interpolation and Q4 must be measured.

### 3.2 A priori conditional query envelope

This envelope is chosen from fixed source formulas before any trajectory
measurement: theta in `[-0.5,0] rad`, omega in `[100*pi/30,600] rad/s`, V=4,
rho=1.18, mu=1.79e-5, T=293.15. It is **conditional**, not a new production
domain, control or a claim the trajectory stays in that box. Geometry has
R=0.11 m, hinge=0.085 m, hub=0.016 m. Positive cosine projection in that theta
box keeps queried radii within `[0.016,0.11]`; nominal/inserted-hinge station
chords are positive convex interpolants within `[0.001,0.1] m` and twists
within `[-1.5,1.5] rad` (actual station extrema are narrower). The projection
keeps chord/twist unchanged. The initial theta=-0.2 and omega=400*pi/30 are
inside this envelope; no guarantee is made for later stages.

In real BEM, U=omega*r, E=hypot(V,U), and
`(wa,wt)=0.5*(V,U)+0.5*E*(sin(psi),cos(psi))`. Triangle inequality gives
W=hypot(wa,wt)<=E for **every** trial psi, not only a converged root.
The positive branch searches between atan2(V,U) and pi/2 minus its existing
angle tolerance. Thus wt>=U/2, wa>0, W>=U/2 and phi=atan2(wa,wt) is in
`[0,pi/2]`. This supplies all three source dimensions:

```text
0.08377580409572782 <= W <= 66.12110101926616 m/s
Mach <= 66.12110101926616 / sqrt(1.4*287.05*293.15)
     = 0.1926426012715746 < 0.2
5.522650772790995 <= Re = rho*W*chord/mu <= 435882.1184510283
-1.5-pi/2 <= alpha = twist-phi <= 1.5
```

The strict margins to support `[0,0.2]`, `[1,1e6]`, and ALPHA are substantial;
certify the inequalities with outward interval/rational evaluation before
freeze, including binary64 query evaluation and projection/interpolation
roundoff. The displayed decimals are explanatory evaluations of the source
bounds, not an exact-rounding theorem. All initial trial query envelopes are
recorded below. Outside this state/geometry envelope, its coverage proof ends;
every actual query still faces `bounds="error"`. No unlimited BEM-query
coverage, solver convergence or partition smoothness is claimed. A later
source failure blocks the fixture; tables are not enlarged from trajectory
results. Stage-domain failures, source ledger and sample matching remain.

### 3.3 Complete candidate literal and content digests

Appendix A is the complete manifest: all effective candidate23 mechanics,
nonzero hinge rate, motor, environment, actuation, controls, BEM settings,
source identity and design-draft TOML, with only `polars` replaced. Decimal
float tokens denote the shown binary64 values; do not infer missing defaults.
The exact base `_binding(initial_angular_velocity_rad_s=0.01)` reconstruction
is tested in the scratch recipe; its sealed payload differs only in `polars`.
Actuation times remain `(0,0.004)` s, so the real-source trajectory duration
would remain 0.004 s if selection were later possible.

Canonicalization: recursively replace each float leaf by
`{"binary64": float.hex(value)}`; preserve integers, booleans and strings;
serialize sorted keys, compact separators `(',',':')`, ASCII escaping,
`allow_nan=False`, UTF-8, no trailing newline. Arrays preserve order. Hash
with SHA-256. This avoids using decimal formatting as an exact residual oracle.

| Content | SHA-256 |
| --- | --- |
| `dataclasses.asdict(SCHEDULE)` polar-source manifest | `1b15c2fb8428968642a56f097d9be5ffb19af5982a8cf8f16cb753fc11bdf754` |
| Complete Appendix A manifest | `c2061c293190a5fec947230b89c98c553da22aab738b6146c54fd49955dfb547` |
| Main v1 sealed candidate28 binding, existing seal format | `1c814e7a4b4b5229a56e91679a6920567676439efd471fbe5277de914e0aca54` |
| Input canonical design file, raw bytes | `a3852e5d14f433528fa9ad63bae26dd076b5136eacf4a7860ef76971eec2afdc` |
| Generated draft, existing seal format | `94553fbeaf4f41a01ee998cb51f13bc6fc34ac2ceecdf8b6d482cd63ea03c3f0` |

The v1 implementation/service IDs in Appendix A describe the **measured main
binding**, not a Radau v2 seal. A future v2 production request must record its
actual v2 identity and a separate sealed digest; it cannot reuse this v1 hash.
Content hashes identify inputs, not acceptance, authentication or qualification.

### 3.4 Measured initial-source feasibility: another blocker remains

Scratch-only recipe in Appendix B used main `4cf0d0e...`, Python 3.12.14,
NumPy 2.3.5, SciPy 1.17.0. Script SHA-256:
`e69047e90bc09c2b2c779222c1e4c5557b1ea5be6851a41e51cff21f785b493c`.
It calls the real algebraic motor and real BEM/mapper at t=0 only, with
observing wrappers forwarding unchanged arguments/results. No integration,
production/reference trajectory, DOP853 or selection was run. Local 1.17.0
results are not attributed to CI's 1.15.3/1.17.1 environments.

The motor passed. One real BEM completed four annuli, with 43 polar queries:

| Quantity | Observed initial-query range |
| --- | --- |
| Mach | `[0.012306553842800508,0.016583659472520842]` |
| Reynolds | `[4270.160319888545,6629.080317420814]` |
| Alpha rad | `[-0.8005705217350787,-0.6439934314763611]` |
| Clamped dimensions | None |
| Rotor thrust N / resisting torque N m | `0.018485821654192467` / `0.0020682088425557793` |

Mapping then raised `PlanarProjectedMaterialLoadError: movable-span coverage
is incomplete: integration ends inboard of the projected tip.`, wrapped by
`Cmm2TransientFailure: CMM-2 aerodynamic source evaluation failed.`.
The projected tip is `0.10950166444603104 m`; BEM station-span endpoint is
`0.1073455179747803 m`; measured gap is `0.0021561464712507444 m`.
Source geometry explains it a priori: last station is r/R=0.98, so the gap is
`(1-0.98)*0.11*cos(0.2)=0.0022*cos(0.2) m`. This is missing geometric coverage,
not terminal two-ULP normalization. Changing polar data cannot fill it.

**Disposition: CANDIDATE REJECTED: SOURCE DOMAIN / NOT SELECTED.** Q2
preflight detectability, mapped Q4, partition margins and trajectories are
unmeasured. The second requested repeated evaluation is not reached after
the first map fails. Keep this failed result in the manifest review record;
do not silently modify geometry, radial_domain, mapper coverage or coefficients.
The requested polar-only amendment is concretely specified but insufficient
for selectable C2V-09 evidence with retained candidate23 settings. A separate
reviewed fixture-scope decision is necessary before any freeze/implementation;
that earlier candidate28-only scope did not authorize a geometric extension.
The subsequent explicit authorization appends candidate29 in the
[separate declaration](cmm2_c2v09_candidate29_proposal.md); candidate28 and its
rejection are preserved without revision.

## 4. Complete proposed Phase A/B selector and unchanged gates

The earlier proposed v2 walk is 00…27 then28. The current proposed v3
walk appends29: **00…27,28,29**, without trajectory metrics; its complete
[manifest and initial-only plan](cmm2_c2v09_candidate29_proposal.md) are separate.
No historical candidate is changed. Phase A
reconstructs the exact literals and validates all used inputs and seals against
the corresponding historical/new manifests. Construction, sealing or binding
mismatch means CONTRACT BLOCKED; stop, do not skip a supposedly committed input.

Phase B is initial-state-only and must implement **all** frozen section-11
requirements. For each constructible candidate:

1. Evaluate the real PR-07 motor, fresh real FoldableBEM, and accepted planar
   mapper. Capture full source query envelopes and cause chains. Expected
   motor/BEM/map domain or convergence rejection records SOURCE DOMAIN and
   continues. Unexpected exception, provenance/seal inconsistency blocks.
2. Independently assemble binary64 M/b from declared mechanics and fresh
   lower-layer loads. Solve its exact Fraction represented system and compute
   Q2 row backward errors, exact represented residual, kappa/rho and
   B_abs_correct. Use `prc_represented_forward_v1`, factor two and its zero
   branch unchanged. Production Schur/mass builder is not the equation oracle.
3. Measure q_theta and raw-versus-mapped acceleration gaps against that same
   B_abs_correct, in acceleration units, exactly as frozen section 11. Use
   the same BEM evaluation for raw positive torque and mapped signed Q_phi.
   Compute independent mechanical dE/dt and frozen P_scale_09/U_P09; require
   `abs(N*q_theta*theta_dot)>U_P09`. No fitted detectability threshold.
4. Record fold/shaft margins against frozen S_theta(0)/S_omega(0). Record
   mapped interval/hinge-cell/radial-midpoint boundary distances and frozen
   radius uncertainty `abs(s_tip*sin(theta0))*S_theta(0)+64 ULPs` of the
   specified radius scale. Require the original strict margin inequalities.
   Insufficient margin/detectability records PREFLIGHT PREDICATE and continues.
5. Run actual repeated real BEM **and mapper** calls with identical physical
   and numerical inputs but a verified changed evaluation index/source
   metadata. Verify that changed metadata enters actual BEM/map source inputs;
   differing report/source IDs alone do not prove this. Observing wrappers
   call real functions unchanged. Compare eight-byte `struct.pack('!d',...)`
   values of thrust, whole-rotor mapped Q_phi and one-tip q_theta, including
   signed zero. Any numerical mismatch is PRODUCTION DEFECT / CONTRACT BLOCK;
   stop, no replacement. Record changed metadata and both bit triples.

No candidate is selected until every requirement passes; zero survivors is
CONTRACT BLOCKED. Only then persist the canonical **complete** selection
record before invoking any trajectory routine: contract head, both manifest
identities, policy version, ordered input digests/dispositions/cause chains,
controls, all preflight metrics, selected index and actual sealed request
hash, Q2 values, detectability, domain/partition margins and Q4 bit evidence.
Later evidence must bind to its selection_record_sha256. Reject/incomplete
records must not label a provisional candidate selected.

After separately authorized implementation, the independent DOP853 A/B
reference uses fresh lower-layer PR-07/BEM/map evaluations at its own states;
independent M/b assembly and represented solve; no production Schur or PR-B
private builder as equation oracle, and no production ledger as force oracle.
Levels, state scales, controls, fixture order and `max e_j<=1` stay unchanged.
Stabilization must be remeasured at actual new production sample times.
Index/ledger length/hash sequence equality across integrators is not required.
No candidate substitution follows favorable/unfavorable trajectory results.

## 5. Affected sections and before/after dependency statements

This is an amendment map, **not edits to those normative sections**.

| Contract section | Current frozen policy | Proposed change, only after future approval |
| --- | --- | --- |
| Radau 3, cubic/time normalization | Exact represented cubic, direct Fraction T_old/H | Preserve; certify both relative/public rounding cells and exact coordinates |
| Radau 4, contact stationary/breach | All certified candidates, direction, earliest event, fail closed | Preserve; two-neighbor choices cannot skip unresolved classification or hide breach |
| Radau 5, conversion/identity/domain | Converted time inside frozen allowance and accepted interval; full audit | Separate root H*D from Q_r/Q_p; fixed neighbor order, collision/order certificates, audit through actual public coordinate |
| Radau 6, root budgets | Shared accepted-interval counters; 32 recursion / 80 refinement | Preserve all charges/limits, including option/refinement retries; no reset/new control |
| Radau 7 / PR-C 8 C2V-07 | Frozen T_allow and unchanged state gates | Add exact Q_r+Q_p only after H*D<=unchanged U_root_time; root/state tolerances unchanged |
| Radau 8, source/Q4/DOP853 | All actual RHS/Jacobian/aero calls budgeted; fresh oracle | Preserve; remeasure on actual sample times, no nfev-only accounting |
| Radau 9/10, dependency/acceptance map | Frozen design, future implementation verification | Add feasibility proposal dependency before any changed-policy implementation |
| PR-C 7, ordinary trajectories | Frozen state scales and oracle stabilization | Preserve, except explicitly scoped C2V-07 returned-time arithmetic above |
| PR-C 8 C2V-09 / 11 / 15 Q3 | Complete v1 list, none pass means blocked/no new candidate | Proposed v2 appends28; current proposed v3 appends29 via its separate manifest; no in-place alteration of00…27 or historical Q3 closure |
| PR-C 10 Q2 / 15 Q1,Q2,Q4,Q5 | Accepted equation/residual policies; Q4 measurement pending; Q5 open | No technical change; new candidate still requires all preflight measurements |
| PR-C 13/16, evidence/critical manifest | v1 fixture identity and pre-result selection record | Retain28 proposed v2 manifest/hashes; append29 proposed v3 manifest, draft and seal identities; retain v1 evidence provenance |
| PR-C 17/18, implementation/acceptance | Verification not established, failure remains visible | Changed-policy implementation requires later review/freeze/authorization, never retroactive PASS |
| PR-A Termination / frozen Radau pointer | Main RK45/v1 and existing fail-closed behavior | Future CMM-2 adapter may use the proposed timing policy only after freeze; CMM-1 remains RK45 |
| PR-B Call, Seal/report, frozen Radau pointer | Main source-bound v1, ledger/sample matching | Future v2 seals identify actual numerical policy and bind certificates; no legacy hash reuse |

C2V-01…06 and C2V-08…12, C2V-02 bridge, Q1–Q4 mathematics, energy,
contact angle/direction rules, load signs, shaft/fold domain, source provenance,
RHS/aero/Jacobian accounting, segment boundaries and every work ceiling remain
unchanged except the explicitly proposed C2V-09 **construction/selection
version**. Q5/runtime/partition/minimum-SciPy characterization remains pending.
The synthetic table is a verification source replacement, not relaxation of
source validity. PR #81's frozen trajectory failures remain failures.

## 6. Acceptance prerequisites and reserved work

This docs-only proposal can be reviewed as a proposal with an explicit
unresolved fixture blocker. It cannot be accepted as a feasibility-complete
contract ready for implementation or frozen candidate manifest.

Required sequence:

1. Independent mathematical review of the bound, certified finite neighbor
   selection/cells/ties, both coordinate predicates, root identity/order,
   large-origin audit/collision failures, and unchanged state/work gates.
2. Independent fixture review of the full literal/digests/source envelope and
   **resolution by separately authorized scope** of the station-span coverage
   defect. If geometry/settings must change, create a new explicit proposal
   before measurements; never rewrite28 or old candidates from trajectory results.
3. Freeze only the independently reviewed feasible amendment/manifest with
   actual technical head and provenance. This PR remains PROPOSED; no automatic
   freeze follows its publication or baseline CI.
4. Obtain separate implementation authorization. Future production scope is
   only the CMM-2 conversion/certificate adapter, shared budget accounting and
   scoped report identity; CMM-1, equations, oracle, controls and thresholds stay.
5. Later behavior TDD must cover actual captured cubic obstruction, exact1/3
   upper-neighbor witness, representable singleton, ties/subnormals/exponent
   boundaries, both coordinates, large-origin collision/overflow/no-advance,
   interval equality, intervening event/domain boundaries, unresolved decisions,
   mechanical breach/stationaries and budget exhaustion without resets/sampling.
6. Later verification implements the complete Phase A/B record, real metadata
   Q4, detectability/margins and independent DOP853. Only after a feasible
   manifest is reviewed/frozen may production/reference trajectories of new
   candidates be run. Full C2V gates, provenance/regressions and actual SciPy
   1.15.3/1.17.1 environments are required. Minimum supported SciPy remains
   unmeasured until separately characterized.

Document/link/whitespace checks and exact-head **main baseline** CI validate
this docs change; they are not Radau implementation or PR-C numerical evidence.
No production, tests, fixtures, workflows or ADR files change. Historical
acceptance records are retained byte-for-byte; only explicit proposal pointers
are appended. No ADR-009 acceptance or qualification promotion follows.

## Appendix A. Complete proposed candidate manifest

The JSON below is the manifest hashed by the rule in section 3.3. It includes
the complete generated draft TOML as a string, not a mutable reference to a
future helper. Its `effective_binding` represents the measured main-v1 seal.

```json
{
  "base": "4cf0d0ea017fa824ba8d4a063ceddd015dae09d6",
  "candidate_id": "C2V09-28",
  "draft_toml": "schema_version = 1\n\n[design]\nid = \"TIP_HINGED_250_CANONICAL_DRAFT\"\ndescription = \"Unqualified UI draft derived from TIP_HINGED_250_CANONICAL\"\n\n[blade]\ndiameter = \"220.0 mm\"\nhub_radius = \"16.0 mm\"\nblade_count = 3\n\n[[blade.stations]]\nr_over_R = 0.2\nchord = \"24.64 mm\"\ntwist = \"31.0 deg\"\nairfoil = \"NACA0012\"\n\n[[blade.stations]]\nr_over_R = 0.4\nchord = \"22.88 mm\"\ntwist = \"24.000000000000004 deg\"\nairfoil = \"NACA0012\"\n\n[[blade.stations]]\nr_over_R = 0.6\nchord = \"20.240000000000002 mm\"\ntwist = \"17.0 deg\"\nairfoil = \"NACA0012\"\n\n[[blade.stations]]\nr_over_R = 0.8\nchord = \"14.96 mm\"\ntwist = \"10.0 deg\"\nairfoil = \"NACA0012\"\n\n[[blade.stations]]\nr_over_R = 0.98\nchord = \"7.04 mm\"\ntwist = \"5.0 deg\"\nairfoil = \"NACA0012\"\n\n[[airfoils]]\nid = \"NACA2412\"\nsource = \"analytic_naca_4_digit\"\n\n[[airfoils]]\nid = \"NACA0012\"\nsource = \"analytic_naca_4_digit\"\n\n[[operating_conditions]]\nid = \"hover_7100_rpm\"\nangular_speed = \"3999.9999999999995 rpm\"\nforward_speed = \"4.0 m/s\"\nair_density = \"1.18 kg/m^3\"\ndynamic_viscosity = \"1.79e-05 Pa*s\"\ntemperature = \"293.15 K\"\npressure = \"100000.0 Pa\"\n\n[hinge]\nradius = \"85.0 mm\"\naxial_offset = \"0.0 mm\"\ntangential_offset = \"0.0 mm\"\naxis_azimuth = \"0.0 deg\"\naxis_elevation = \"90.0 deg\"\nstowed_angle = \"-180.0 deg\"\ndeployed_angle = \"0.0 deg\"\nstop_angle = \"0.0 deg\"\n\n[motor]\nid = \"REFERENCE_980KV\"\nkv = \"980.0 rpm/V\"\nresistance = \"0.06 ohm\"\nno_load_current = \"1.2 A\"\nmax_current = \"30.0 A\"\n\n[manufacturing]\nprocess = \"FFF\"\nmin_wall_thickness = \"1.2 mm\"\nmin_trailing_edge_thickness = \"0.8 mm\"\nbuild_orientation = \"to_be_verified_by_coupon_tests\"\n\n[metadata]\nartifact_class = \"unqualified_design_draft\"\nnote = \"Airfoil, chord, and twist values are initial schema examples, not validated design claims.\"\npreview_fold_angle = \"-59.999999999999993 deg\"\npreview_fold_angle_semantics = \"UI preview pose; not a hinge stop or a physical result\"\nproject = \"PyFoldable\"\nsource_design_id = \"TIP_HINGED_250_CANONICAL\"\nsource_design_sha256 = \"a3852e5d14f433528fa9ad63bae26dd076b5136eacf4a7860ef76971eec2afdc\"\nstowed_envelope_requirement = \"140 mm\"\n",
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
    "draft_sha256": "94553fbeaf4f41a01ee998cb51f13bc6fc34ac2ceecdf8b6d482cd63ea03c3f0",
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
    "source_sha256": "a3852e5d14f433528fa9ad63bae26dd076b5136eacf4a7860ef76971eec2afdc",
    "spring_stiffness_nm_rad": 0.0,
    "surface_path_clearance": null,
    "system": {
      "resistance_ohm": 0.01
    },
    "throttle": 0.1,
    "upper_stop_rad": 0.0,
    "viscous_damping_nm_s_rad": 0.0
  },
  "inherited_candidate": "C2V09-23",
  "selection_policy": "prc_c2v09_ordered_candidates_v2_proposed"
}
```

## Appendix B. Exact scratch initial-source recipe

This is a documentation code block, not an executable fixture committed to
the repository. SHA-256 is over the UTF-8 block contents, with its final
newline. Run only initial-source checks after independent review of the
intended inputs; the recorded run predates any new candidate trajectory.
It expects repository path as argv[1], available pytest for loading the base
helper, and writes temporary JSON to /tmp. Its failed call preserves partial
BEM metrics and the underlying mapper cause; no success/selection is asserted.

```python
import importlib.util, sys, json, math, hashlib, platform, dataclasses
from pathlib import Path
import numpy, scipy
ROOT=Path(sys.argv[1]).resolve()
spec=importlib.util.spec_from_file_location('fixture_source', ROOT/'tests/application/test_cmm2_coupled_transient_service.py')
f=importlib.util.module_from_spec(spec);spec.loader.exec_module(f)
from pyfoldable.core.models import PolarTable
from pyfoldable.core.polar import PolarFamily
from pyfoldable.core.polar_spanwise import SpanwisePolarSchedule,SpanwisePolarAnchor
import pyfoldable.application.cmm2_coupled_transient_service as svc
META={'classification':'synthetic_test_fixture','owner':'PyFoldable','purpose':'C2V09-28 source-domain verification only','revision':'c2v09-28-synthetic-polar-v1','physical_qualification':False,'experimental_validation':False}
ALPHA=(-float.fromhex('0x1.921fb54442d19p+1'),0.0,float.fromhex('0x1.921fb54442d19p+1'))
TABLES=tuple(PolarTable(airfoil_id='NACA0012',scenario_id='cmm2',reynolds=re,mach=ma,alpha_rad=ALPHA,cl=(0.6,)*3,cd=(0.02,)*3,cm=(0.0,)*3,source='pyfoldable:first-party:c2v09-28-synthetic-polar-v1',metadata=dict(META)) for ma in (0.0,0.2) for re in (1.0,1.0e6))
FAMILY=PolarFamily(TABLES)
SCHEDULE=SpanwisePolarSchedule('cmm2-span',(SpanwisePolarAnchor(0.2,FAMILY),SpanwisePolarAnchor(1.0,FAMILY)))
binding=f._binding(initial_angular_velocity_rad_s=0.01,polars=SCHEDULE)
old=f._binding(initial_angular_velocity_rad_s=0.01)
a=json.loads(binding.context_json);b=json.loads(old.context_json)
assert {k for k in a if a[k]!=b[k]}=={'polars'}
# Digests use exact binary64 hex leaves, no environment-/solver-specific seals.
def canon(x):
 if isinstance(x,float): return {'binary64':x.hex()}
 if isinstance(x,dict): return {k:canon(v) for k,v in x.items()}
 if isinstance(x,(list,tuple)):return [canon(v) for v in x]
 return x
def js(x):return json.dumps(canon(x),sort_keys=True,separators=(',',':'),ensure_ascii=True,allow_nan=False)
polar_literal=dataclasses.asdict(SCHEDULE)
manifest={'candidate_id':'C2V09-28','selection_policy':'prc_c2v09_ordered_candidates_v2_proposed','base':'4cf0d0ea017fa824ba8d4a063ceddd015dae09d6','inherited_candidate':'C2V09-23','effective_binding':a,'draft_toml':binding.draft.toml}
Path('/tmp/candidate28_manifest.json').write_text(json.dumps(manifest,sort_keys=True,indent=2,allow_nan=False)+'\n')
Path('/tmp/candidate28_polar.json').write_text(json.dumps(polar_literal,sort_keys=True,indent=2,allow_nan=False)+'\n')
# Observe real calls, preserving inputs and output objects. No trajectories.
real_bem=svc.solve_foldable_bem_rotor;real_map=svc.map_foldable_bem_aero_loads
bem_results=[];maps=[]
def bem(*args,**kw):
 out=real_bem(*args,**kw);bem_results.append(out);return out
def mapper(*args,**kw):
 out=real_map(*args,**kw);maps.append(out);return out
svc.solve_foldable_bem_rotor=bem;svc.map_foldable_bem_aero_loads=mapper
out={'code_head':manifest['base'],'python':platform.python_version(),'numpy':numpy.__version__,'scipy':scipy.__version__,'script_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),'polar_sha256':hashlib.sha256(js(polar_literal).encode()).hexdigest(),'candidate_manifest_sha256':hashlib.sha256(js(manifest).encode()).hexdigest(),'main_v1_binding_sha256':binding.input_sha256,'changed_binding_fields':['polars'],'trajectory_calls':0,'status':'INITIAL SOURCE CHECK ONLY / NOT SELECTED'}
built=svc._build_cmm2_request(binding)
try:
 motor=built.motor_evaluator(0.0,-0.2,0.01,400.0*math.pi/30.0)
 evs=[built.aero_evaluator(0.0,-0.2,0.01,400.0*math.pi/30.0) for _ in range(2)]
 out['motor']=dataclasses.asdict(motor)
 out['evaluations']=[dataclasses.asdict(e) for e in evs]
 out['bem']=[r.as_mapping() for r in bem_results]
 out['mapped']=[m.as_mapping() for m in maps]
except Exception as e:
 out['failure']={'type':type(e).__name__,'message':str(e),'cause_type':type(e.__cause__).__name__,'cause_message':str(e.__cause__)}
 out['bem']=[r.as_mapping() for r in bem_results]
 out['mapped']=[m.as_mapping() for m in maps]
Path('/tmp/candidate28_initial_source.json').write_text(json.dumps(out,sort_keys=True,indent=2,allow_nan=False)+'\n')
print(json.dumps({k:v for k,v in out.items() if k not in ('bem','mapped')},indent=2))
```

Candidate29 was declared and independently reviewed at exact HEAD
`33a59142f0206e1370c9a0c44116f1dd709b35d3` before initial-only source calls.
The [measured initial record](cmm2_c2v09_candidate29_initial_preflight.md)
retains a literal partition-predicate FAIL, despite source/Q2/detectability/Q4
checks passing. Candidate28 still fails mapping; neither candidate is selected
or trajectory-verified. The current proposed ordering is00…27,28,29.

## 7. Cumulative implementation authority and live eligibility

**Prospective authoritative implementation subsection.** This completes the
cumulative design, without implementing or executing it. It becomes the governing
amendment only when a separate status record identifies its independently
approved technical HEAD and records **REVIEWED / FROZEN FOR IMPLEMENTATION —
CMM-2 NUMERICAL FEASIBILITY AMENDMENT** after documentation checks and exact-head
baseline CI pass. A subsequent status-only closure HEAD is not the technical
reviewed HEAD. Until then this subsection remains PROPOSED / NOT FROZEN /
NOT IMPLEMENTED. Even after design freeze, implementation requires separate
authorization; PR #85 remains Draft and unmerged for coordinator review.

The freeze is of the complete conditional implementation design, not successful
candidate selection, a live runtime eligibility result or accepted PR-C evidence.
It supersedes earlier declaration-time statements that this cumulative design
cannot yet be frozen; it does not rewrite their measured failures or assert
every-angle BEM success. The original technical head
`613072514f793f2a1bc65704f9158f536210707f`, C2V-02 arithmetic head
`b840ec55b4d1dd57197b97e91e1a48a7fbe7da0d`, Radau technical head
`2ec4da9acdccc7508fab7c33f289ec9771b2ea65`, v3 scope declaration head
`7718ea58a6286fa398b2295a5b60e417cb94b04e` and bounded certificate review head
`9ccd93eeb8bf7333473f1d647c875de900081227` retain their earlier review scopes.

### 7.1 Dependency and precedence map upon design freeze

The following exact policy identities are retained, including their `_proposed`
suffixes; lifecycle status is recorded separately. There is no implicit policy
rename, new model identity or numerical threshold. The earlier section 3
suggestion to drop a suffix on a future status change is not exercised by this
cumulative freeze. The reviewed technical HEAD pins every referenced definition.

| Layer / locator | Applicable definition and narrowly replaced obligation |
| --- | --- |
| Frozen PR-A/PR-B and [Radau design](cmm2_radau_remediation_contract.md) | Remain the parent model/source-bound/integration, contact, cubic, domain, ledger and budget contracts; main remains RK45/v1 and CMM-1 RK45 is unchanged |
| This document section 2, `cmm2_contact_timestamp_quantization_v1_proposed` | Unchanged root/time triangle accounting, two-neighbor nearest-first selection and refinement restart; supersedes only Radau sections 5/7 and PR-C C2V-07 returned-time conversion/accounting identified in section 5 |
| [Candidate29 declaration](cmm2_c2v09_candidate29_proposal.md) sections 1–3, `prc_c2v09_ordered_candidates_v3_proposed`, plus this document section 4 | Append-only order **00…27,28,29** replaces only the complete-list restriction of frozen PR-C section 11/Q3; original00…27 and candidate28/29 literals and histories are immutable; Phase A/B dispositions and first-passing selection remain |
| [Partition v2](cmm2_c2v09_partition_policy_proposal.md) sections 2–7, `prc_c2v09_partition_provenance_neighborhood_v2_proposed`, explicitly narrowed by [scope v3](cmm2_c2v09_partition_scope_runtime_proposal.md) sections 2–3/5, `prc_c2v09_partition_geometry_scope_v3_proposed` | Replaces exactly this document section 4 item 4's **partition comparison** and the frozen [PR-C section 11](cmm2_numerical_verification_contract.md#11-c2v-09-selection-and-detectability) paragraph beginning “Partition margin:” and ending “Both numbers are recorded.”; the distinct-class rule and complete scope-A certificate below are the replacement |
| This section 7 | Controls cumulative precedence, mandatory live eligibility and future selection/seal provenance; overrides conflicting earlier prospective dependency/status wording only within that scope |

The replacement partition obligation is: certify topology and represented
construction provenance throughout exact Theta0 first; retain every original
row, raw distance, uncertainty and literal v1 result; classify only proved
whole-neighborhood construction aliases as STRUCTURAL_IDENTITY; for **every
nonidentical relevant pair** retain the unchanged strict center-distance gate
and stored uncertainty, nearest boundaries across distinct identity classes,
and prove signed separation without zero throughout Theta0. Include all actual
station/spanwise normalized-query branches, the separate kernel-radius path,
mapper ownership and unchanged native terminal guard. Missing or unresolved
proof, independent coincidence, ownership/branch changes, touching or crossing
zero remain BLOCKED. Alias classification never makes a zero v1 row PASS.
The v2 Q4 successor PASS expression is the conjunction of all five checks,
not bit identity alone; its numerical bit gate is unchanged.

Only the partition part of section 4 item 4 is replaced: fold/shaft margins,
all detectability gates, source rejection, Q2 and Q4 rules remain. Frozen PR-C
section 11's later unresolved-partition paragraph and all other obligations
remain unchanged. V3 narrows v2's bundled proof dependency to **A: represented
geometric partition/query/ownership conditional on a valid actual returned
source object**. Initial-state source/preflight B remains independently required.
Universal every-angle nongeometric Mach/Re/alpha coverage or BEM convergence C
is unproved and is not an inherited prerequisite for A. This does not weaken
any actual source-domain/convergence rejection or later callback failure.

Candidate28's mapper rejection, candidate29's literal v1 FAIL/four raw zeros,
historical v2 BLOCKED and all captures, observer errors and proof digests retain
their original policy/head/runtime scope. The approved A certificate is a
later conditional result under v3, not retroactive PASS for those records.
Candidate29 remains **NOT SELECTED** and unchanged, manifest SHA256
`0b37fb45c005d7a046dee6541d1a89e4a0a5cead7434621718c90d191843b7a4`.

### 7.2 Mandatory actual eligibility before relying on scope A

Future executable implementation **MUST establish live eligibility** before
using the [concrete certificate](cmm2_c2v09_partition_runtime_certificate.md)
or recording successful selection. Archived-record replay, a matching Python/
SciPy/libm version label, matching policy names or baseline CI are insufficient.
The live execution must bind and check the conjunction of:

1. The exact independently reviewed/frozen technical HEAD, applicable timestamp,
   selector, partition-v2/scope-v3 definitions and reviewed certificate identities.
   Verify their immutable artifact bytes/digests, their dependency links and
   the certificate's scope; neither a closure HEAD nor an old proof capsule
   substitutes for the actual technical authority.
2. The exact candidate29 manifest, draft and synthetic source identities/bytes;
   source code hashes and the **actual called represented operation graph**,
   operands, branches and copy provenance bound by the certificate. Validate
   actual inputs against the immutable manifest and preserved seal provenance.
   A changed parser, interpolation path, source/mapper, reassociation, fusion,
   substituted object or monkey patch is not cleared by an unchanged label.
   The actual finite validated returned source object must satisfy the existing
   A hypothesis and be the object consumed by the mapper; replay cannot supply it.
3. Exact stored theta0, stored S_theta(0), rational Theta0 endpoints, initial
   non-angle state/settings and every unchanged stored center uncertainty from
   the captured certificate. Compare represented values and provenance, not
   rounded decimals. Changing or recomputing the scale/uncertainty invalidates
   eligibility; the proof covers all represented angles in **that** Theta0.
4. Applicable source/code and CPython/math/libm/libc/loader byte/build identities,
   loaded instructions/constants/wrapper targets, actual selected dispatch and
   the certificate's bound CPU/feature identity. Establish the required binary64
   operation semantics and numerical control state in the executing context:
   RNE ties-even, required SSE/AVX/FMA behavior, DAZ/FTZ off and the recorded
   x87/feature/OS-state conditions. Only identifiers explicitly declared
   nonbinding by the existing certificate, such as ASLR base/APIC scheduling
   number, may differ without altering applicability. Equal version strings,
   equal output samples or the same dispatch address alone do not prove it.

Check the immutable run-wide bindings before any certificate-dependent Phase B
partition evaluation; establish the per-execution dispatch/control/input/source
conditions immediately before and after each affected real evaluation, including
Q4 variants, and verify the returned-object/graph link before relying on its
partition result. Revalidate immediately before canonical successful-selection
recording and future-v2 sealing, and before any later certificate-dependent use.
Permitted Q4 metadata/index deltas must match their separate committed probe
binding while leaving the physical numeric graph unchanged.

Eligibility is valid only for the checked execution context and immutable
binding. Process/thread/runtime migration, resume/reload, module/library/source
replacement, dispatch or feature changes, numerical-control changes, altered
inputs/scale/uncertainty, or inability to establish uninterrupted applicability
invalidates it. Any post-call mismatch invalidates dependent results; a stale
eligibility digest cannot authorize them. Establish a new matching live record
before further use; clearing a mismatch is not inferred from archived replay.
Record the observed mismatch and retained partial evidence as **CONTRACT BLOCKED**;
stop selection rather than skipping candidates or falling back to v1, sampling,
a different runtime or assumed alternate-runtime clearance. Missing eligibility
is an execution block, not a new mathematical defect in the conditional design.

Ordinary Python3.10/SciPy1.15.3 and Python3.11/SciPy1.17.1 baseline CI environments
remain uncertified by this concrete-runtime proof. They cannot select candidate29
through A unless an applicable independently reviewed certificate and live
eligibility are established. No additional mathematical or alternate-runtime
certificate is required for this **bounded documentation closure**; any future
execution outside the existing certificate remains blocked pending its own
separately authorized review, without widening this design's claimed proof.

### 7.3 Canonical pretrajectory record and separate future v2 seal

Before any trajectory routine, the future complete ordered Phase A/B selector
must persist all original section 4 / PR-C11 fields, all candidate dispositions
and partial failures, and actual execution provenance. Successful selection
requires every unchanged initial source, Q2, detectability, domain and conjunctive
Q4 predicate plus the amended partition obligation and live eligibility.
Historical isolated feasibility measurements/replay do not execute that walk
or constitute a successful-selection record. If none pass, CONTRACT BLOCKED;
after selection, no candidate substitution follows trajectory results.

The canonical record must additionally bind these inseparable fields:

| Field group | Required binding |
| --- | --- |
| Technical authority / policy bundle | Actual reviewed technical HEAD, later closure HEAD as separate provenance, exact timestamp/selector/partition-v2/scope-v3 IDs, repository/path/section locators and SHA256 of each referenced artifact's exact UTF-8/LF file bytes **at the reviewed technical HEAD**; canonical policy-bundle digest |
| Immutable input / original provenance | Original00…27 manifest/history, candidate28 manifest/rejection, candidate29 manifest/draft/source digests, unchanged controls, exact Theta0/stored scale/uncertainty, preserved original v1 seal digests; per-candidate actual call-input hashes |
| Reviewed proof | Exact runtime-binding record SHA256 `5a2a8ab62faf7729769ea9dd620ffd07635605ae170ef523c91d3ec560c16a67`, cosine record `7c9fc9cc0def92fb3d4f2c850e63e85ce70821aa562fbc1c9a9ab45f5e12b865`, prior geometric record `0b672af90ee94197489522c45ab173834b893a7a47786c196eed7f0478cb4526`, connection record `80abd1b5d16872a67004a0511fdb8ad40c8d04d5e1319635d1b79459b4280897`, unchanged declaration/recipe digests and approved bounded scope |
| Live applicability / execution | Separate actual runtime-binding and eligibility-record digests, executing code/implementation and loaded binary identities, CPU/selected dispatch/numerical-control observations, context/check sequence and invalidations, actual source object/call and mapper correspondence, Q4 permitted metadata/index inputs and all preflight results |

Policy-bundle and live-eligibility digests use SHA256 of sorted compact ASCII
JSON, UTF-8 without final newline, finite-only values; encode binary64 leaves
as exact hexadecimal strings (preserving signed zero), rational endpoints as
exact numerator/denominator strings. The selection record retains the same
declared canonical encoding and hashes its complete payload before trajectory
entry. The cited historical fenced record/recipe file digests retain their
original final-newline convention. Canonical digests bind content and actual
recorded observations; they do not by themselves prove live applicability.

A **separate future numerical-implementation-v2 seal** must bind that canonical
policy bundle, reviewed proof/runtime-binding digests, live runtime/eligibility
records, selected immutable request and completed initial preflight evidence,
actual implementation/code/environment/source provenance and existing sealed
controls/model/load-map/qualification identities. Its eligibility and actual
payload must be checked by the future prepare/seal validation path. Original
main-v1 and Q4-variant seals remain byte-unchanged historical initial-only
provenance, never relabelled v2. No v2 seal is created by this documentation task.

Hash dependencies are acyclic: complete initial preflight and live eligibility,
then validate/create the future-v2 seal, then write the canonical selection
record binding that actual selected sealed-request digest, then enter any
trajectory routine. The v2 seal does not hash the subsequently created selection
record; no payload contains its own digest. All later evidence must link both
selection_record_sha256 and the applicable v2 seal. Eligibility invalidation
prevents stale records/seals authorizing continued use.

### 7.4 Unchanged gates, review limits and reserved execution

Initial source rejection and cause-chain recording, bounds="error", all Q2
represented residual/row/kappa/rho/factor-two/zero-branch rules, load/work
detectability, real metadata/index Q4 conjunction, fold/shaft margins, source
ledger/sample matching and every work ceiling remain unchanged. No new user
control, source success inference or unbudgeted RHS/aero/Jacobian call is allowed.
DOP853 A/B independence/levels, fixtures00…29 order, controls, state tolerances,
C2V-02 arithmetic bridge and trajectory `max e_j<=1` are unchanged; only the
explicit section 2 C2V-07 returned-time accounting applies upon freeze.

Later callback/domain/budget failures remain failures. The initial A certificate
does not clear later dense intervals: complete continuous represented contact/
fold/shaft audits, first-event identity/order/direction, public-time audit extent,
interior crossings/tangencies and unresolved ordering retain their frozen rules.
No sampling-only clearance or source/fixture substitution is permitted. Q5,
runtime/partition characterization and minimum-SciPy evidence remain pending.

This task performs **no** production implementation, executable fixture, new
source call, ordered selection, trajectory or future v2 seal. An independent
exact-HEAD reviewer must explicitly approve readiness to freeze the complete
conditional design, not merely publication or an arithmetic replay. After that
approval and technical-head checks/CI, a separate **status-only** closure commit
records the approved technical HEAD without changing any policy, candidate,
timestamp arithmetic or proof digest; closure-head checks and fresh CI follow.
No implementation authorization or accepted PR-C evidence follows. PR #81/#84
remain untouched; ADR-009 is not accepted, `physical_qualification=false`,
PR-06C unresolved; no GEOM, calibration or experimental-validation promotion.

## 8. Conditional design-freeze status record — 2026-10-02

Status: **REVIEWED / FROZEN FOR IMPLEMENTATION — CMM-2 NUMERICAL FEASIBILITY AMENDMENT**.
Implementation: **NOT IMPLEMENTED / NOT AUTHORIZED BY THIS DESIGN FREEZE**.

Actual independently reviewed technical HEAD:
`fd55fa97676c84c896511765e94561a706252239`.
Technical tree: `6b73f38cc1d7d42f569bd3577326315b31a1f921`.
Base: `4cf0d0ea017fa824ba8d4a063ceddd015dae09d6`.

The separate read-only automated reviewer explicitly returned **APPROVE FOR
CONTRACT FREEZE**, assessing the complete conditional design and section 7's
precedence, live eligibility, provenance/seal sequence and preserved gates.
New blockers and non-blocking findings: none. This is not a submitted GitHub
review and does not establish live execution eligibility or production evidence.
Earlier reviewed provenance recorded in section 7 remains unchanged.

Technical-head document/link/whitespace/JSON/Python-fence/digest checks passed:
83 historical fenced records preserved, 11 certificate artifact digests and
candidate/capsule digests verified, 19 added links/anchors checked, unrelated
CSV bytes preserved. Exact technical-head baseline CI passed:

- [push 36936347164](https://github.com/Poyqraz/PyFoldable/actions/runs/36936347164)
- [pull_request 36936354877](https://github.com/Poyqraz/PyFoldable/actions/runs/36936354877)

Both runs succeeded on Python3.10 and3.11; every job reported 1811 passed,
9 skipped, 37 subtests passed. GitHub review/comment collections were checked
after that CI and contained no entries. These are baseline regression checks,
not concrete-runtime eligibility or PR-C verification.

This later **status-only closure commit is not the reviewed technical HEAD**.
Its exact SHA is supplied by Git history and PR metadata, avoiding a self-hash.
Its diff changes status/provenance only; section 7 and every prior policy,
candidate, timestamp and proof artifact remain unchanged. Section 7's approved
text SHA256 (UTF-8/LF, exactly one final newline) is
`524c7402fb0cc3972a18bdadf83bc89b5d86bcbadafd7a3ab0392d7489443b92`.
Closure-head document/digest checks and fresh baseline CI remain completion
requirements; a technical-head check does not cover a later commit.

The frozen design requires future live eligibility, full initial ordered
preflight and separate-v2 sealing/selection provenance under section 7; none
has been executed here. Candidate29 is unchanged / NOT SELECTED. Original
candidate28 rejection, literal v1 FAIL and historical v2 BLOCKED remain.
PR #85 remains Draft/unmerged for coordinator bounded-delta review. No production
implementation is authorized; main remains RK45/v1. PR #81/#84 are untouched;
accepted PR-C evidence is absent, ADR-009 remains unaccepted and
physical_qualification=false. Q5, later runtime/partition/dense-interval and
minimum-SciPy evidence remain pending within their stated scopes.
