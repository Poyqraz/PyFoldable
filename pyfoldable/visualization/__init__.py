"""2D engineering schematics for foldable propeller states (matplotlib optional)."""

from .geometry_2d import (
    annotation_lines,
    blade_polylines,
    effective_radius_circle,
    open_reference_polylines,
    plot_limits,
)
from .io import join_visual_states, read_variant_parameters_csv, state_for
from .state import PropellerVisualState

__all__ = [
    "PropellerVisualState",
    "annotation_lines",
    "blade_polylines",
    "effective_radius_circle",
    "join_visual_states",
    "open_reference_polylines",
    "plot_limits",
    "read_variant_parameters_csv",
    "state_for",
]
from .propeller_25d import (
    PREVIEW_QUALIFICATION,
    PreviewBladeStation,
    PropellerPreviewMesh,
    PropellerPreviewSpec,
    build_propeller_preview_mesh,
    naca4_section_loop,
)

__all__ = [
    "PREVIEW_QUALIFICATION",
    "PreviewBladeStation",
    "PropellerPreviewMesh",
    "PropellerPreviewSpec",
    "build_propeller_preview_mesh",
    "naca4_section_loop",
]
