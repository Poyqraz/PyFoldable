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
