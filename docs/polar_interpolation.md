# Polar tables and interpolation

`PolarTable` stores one angle-of-attack sweep at a declared Reynolds number, Mach
number, source, and scenario. `PolarFamily` combines compatible tables for one
airfoil and one scenario.

Interpolation rules are explicit:

- angle of attack: linear;
- Reynolds number: log-linear;
- Mach number: linear;
- default out-of-bounds behavior: error;
- optional out-of-bounds behavior: clamp and report the clamped dimensions;
- extrapolation: unsupported.

```python
from pyfoldable.core import PolarFamily, load_polar_csv

low = load_polar_csv("naca2412_re100k.csv", airfoil_id="NACA2412", reynolds=100_000)
high = load_polar_csv("naca2412_re200k.csv", airfoil_id="NACA2412", reynolds=200_000)
family = PolarFamily((low, high))
result = family.query(alpha_rad=0.05, reynolds=150_000, mach=0.0)
```

`scenario_id` prevents clean, rough, tripped, or otherwise incompatible polar sets
from being blended accidentally. Query results retain contributing sources and list
which dimensions were interpolated or clamped. Provider confidence, transition
settings, roughness, solver version, and experimental provenance belong in each
table's metadata until provider-specific adapters define stronger typed contracts.

## Provider-backed family generation

`PolarFamilyGenerationPlan` expands one request template into a complete rectangular
Mach/Reynolds grid. The template must describe the first cell. Grid axes must already be
strictly increasing; the generator never reorders ambiguous user input.

```python
from pyfoldable import (
    NeuralFoilProvider,
    PolarFamilyGenerationPlan,
    XfoilProvider,
    generate_polar_family,
)

plan = PolarFamilyGenerationPlan(
    request_template=request,
    reynolds_grid=(100_000.0, 200_000.0, 400_000.0),
    mach_grid=(0.0,),
)
generated = generate_polar_family(
    (XfoilProvider(), NeuralFoilProvider()),
    plan,
    cache=cache,
    health_registry=health,
)
family = generated.family
```

Complete generation is deliberately sequential and fail-fast. It requires a complete
provider result for every cell and returns cells in Mach-major, Reynolds-minor order.
An incomplete provider result is first rejected by the orchestration qualification gate,
so another configured provider can satisfy the same cell. Each accepted cell retains
the original `PolarGenerationResult` beside its canonical `PolarTable`, including cache,
retry, fallback, health, warning, and backend provenance. If a cell fails,
`PolarFamilyGenerationError` exposes the successful prefix and the exact failed request.

For an exhaustive batch report, select `collect_all` explicitly:

```python
from pyfoldable import (
    PolarFamilyBatchPolicy,
    generate_polar_family_batch,
)

batch = generate_polar_family_batch(
    providers,
    plan,
    policy=PolarFamilyBatchPolicy(
        failure_mode="collect_all",
        subgrid_policy="complete_axes",
    ),
    cache=cache,
    health_registry=health,
)
```

`batch.cells` and `batch.failures` together cover every planned position. Failures retain
the complete provider-attempt trail and, when the last candidate was incomplete, its
point statuses, rejected indices, and qualification decision. The default
`subgrid_policy="none"` never creates a family from sparse successes. `complete_axes`
considers only two verifiable Cartesian candidates: every complete Mach row across the
full Reynolds axis, or every complete Reynolds column across the full Mach axis. It
chooses the larger candidate deterministically and returns `family=None` when neither
exists. This makes any interpolation across a reduced grid an explicit caller decision.
