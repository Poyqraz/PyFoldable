# Airfoil coordinate input

`pyfoldable.core.load_airfoil_coordinates()` converts coordinate files into the
canonical `AirfoilDefinition` used by future polar and BEM layers.

Supported inputs:

- UIUC/Selig DAT: upper trailing edge to leading edge, then lower trailing edge;
- Lednicer DAT: upper leading edge to trailing edge, followed by lower leading edge
  to trailing edge, with the two surface counts declared after the name;
- CSV: `x` and `y` headers (additional columns are ignored) or two headerless columns.

The reader ignores `#` comments, removes consecutive duplicate points, translates and
scales the geometry to unit chord, and emits one order:

```text
upper trailing edge -> leading edge -> lower trailing edge
```

It rejects malformed rows, inconsistent Lednicer counts, non-consecutive duplicates,
non-monotonic surface ordering, self-intersections, crossed upper/lower surfaces, and
zero-thickness geometries. Open trailing edges are valid and recorded rather than
silently closed.

```python
from pyfoldable.core import load_airfoil_coordinates

airfoil = load_airfoil_coordinates("profiles/e387.dat")
print(airfoil.metadata["maximum_thickness_ratio"])
print(airfoil.metadata["trailing_edge"])
```

Audit metadata includes the detected format, original and normalized point counts,
removed duplicate count, trailing-edge gap, thickness metrics, canonical order, and
SHA-256 of the source text.

Format behavior follows the [UIUC Airfoil Data Site](https://m-selig.ae.illinois.edu/ads.html):
Selig coordinates wrap from the upper trailing edge around the leading edge, while
Lednicer coordinates list the upper and lower surfaces separately from leading edge
to trailing edge. UIUC `#` documentation comments are accepted anywhere in a file.
