"""Optional DUST–MBDyn–preCICE dynamic aero-mechanical route.

Nothing in this package imports preCICE, MBDyn bindings or h5py in the
application process. External solvers run as separate processes described by
an operator toolchain manifest; an installation without them keeps every
existing workflow, including the fully deployed BEM route.
"""

SCHEMA_VERSION = 1
MODEL_ID = "pyfoldable_dust_mbdyn_precice_segmented_rigid_v1"
