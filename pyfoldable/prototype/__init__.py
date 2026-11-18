"""Manufacturing geometry of the printable segmented folding propeller (first physical prototype).

The repository keeps three geometry roles apart:

- display mesh: ``pyfoldable/visualization/blade_surface.py`` (lofted triangles for plots, no joint design);
- mechanical model: ``pyfoldable/dynamics/fold_cycle.py`` (rigid distal segment about a pin, scalar CG distance);
- manufacturing geometry: this package (B-rep solids through build123d/OpenCASCADE, exported as STEP/STL/3MF).

The CAD kernel is the optional ``[cad]`` extra; ``design``, ``loads`` and ``strength`` import without it.
"""
