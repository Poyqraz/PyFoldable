"""Mass properties from the solids and a declared internal-structure model (estimates until printed parts are weighed).

Printed part: m = ρ (V_shell + f (V − V_shell)) with V_shell = min(V, A·w) (perimeter walls w over the surface area A,
infill fraction f inside). The CG and inertia are those of the solid scaled to that mass: exact for f = 1 (the
recommended solid blade), an approximation otherwise (the shell carries relatively more inertia). Hardware: steel,
uniform. Units: g, mm, g·mm² (convert with ``to_si``).
"""
from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np

from .design import MATERIALS, STEEL, PrototypeDesign


@dataclass(frozen=True)
class MassProps:
    mass_g: float
    cg_mm: tuple
    inertia_cg_g_mm2: tuple          # 3×3 inertia tensor about the CG (positive-definite convention)
    volume_mm3: float
    method: str

    @property
    def I(self):
        return np.array(self.inertia_cg_g_mm2, dtype=float)

    def second_moments(self):
        """∫ r rᵀ dm about the origin [g·mm²]."""
        c = np.array(self.cg_mm, dtype=float)
        I = self.I
        return 0.5 * np.trace(I) * np.eye(3) - I + self.mass_g * np.outer(c, c)

    def inertia_about(self, point_mm):
        c = np.array(self.cg_mm, dtype=float) - np.array(point_mm, dtype=float)
        return self.I + self.mass_g * (c @ c * np.eye(3) - np.outer(c, c))


def solid_props(shape):
    """(volume mm³, surface area mm², centroid mm, inertia about the centroid for unit density mm⁵)."""
    from OCP.BRepGProp import BRepGProp
    from OCP.GProp import GProp_GProps
    p = GProp_GProps()
    BRepGProp.VolumeProperties_s(shape.wrapped, p)
    m, c, M = p.Mass(), p.CentreOfMass(), p.MatrixOfInertia()
    I = np.array([[M.Value(i, j) for j in (1, 2, 3)] for i in (1, 2, 3)])
    return float(m), float(shape.area), (c.X(), c.Y(), c.Z()), I


def printed(shape, d: PrototypeDesign) -> MassProps:
    pm = d.print_model
    rho = MATERIALS[pm.material]["density_g_cm3"] / 1000.0          # g/mm³
    V, A, c, I = solid_props(shape)
    shell = min(V, A * pm.wall_mm)
    m = rho * (shell + pm.infill_fraction * (V - shell))
    method = (f"{pm.material} ρ={rho * 1000:.2f} g/cm³, doluluk {pm.infill_fraction:.0%}, duvar {pm.wall_mm} mm"
              + ("" if pm.infill_fraction == 1 else " (atalet katı parça ölçeklenerek: yaklaşık)"))
    return MassProps(m, c, tuple(map(tuple, I * (m / V))), V, method)


def steel(shape) -> MassProps:
    rho = STEEL["density_g_cm3"] / 1000.0
    V, _, c, I = solid_props(shape)
    return MassProps(rho * V, c, tuple(map(tuple, I * rho)), V, f"çelik ρ={STEEL['density_g_cm3']} g/cm³")


def combine(items, method="toplam") -> MassProps:
    m = sum(p.mass_g for p in items)
    c = sum(p.mass_g * np.array(p.cg_mm) for p in items) / m
    I = sum(p.inertia_about(c) for p in items)
    return MassProps(m, tuple(c), tuple(map(tuple, I)), sum(p.volume_mm3 for p in items), method)


def to_si(p: MassProps):
    """(kg, m, kg·m²)."""
    return p.mass_g / 1000.0, np.array(p.cg_mm) / 1000.0, p.I * 1e-9


def fold_mechanism_equivalent(distal: MassProps, d: PrototypeDesign) -> dict:
    """Values for ``dynamics.fold_cycle.FoldMechanism`` (rigid distal about the pin) and what it cannot represent.
    Fold v1 puts the CG on the span line through the pin; the chordwise CG offset is reported separately because it
    sets the deployed moment onto the open stop (``loads``)."""
    px, py = d.connection.pin_x_mm, d.connection.hinge_radius_mm
    cx, cy, cz = distal.cg_mm
    I = distal.I
    return {
        "mass_kg": distal.mass_g / 1000.0,
        "cg_from_hinge_m": math.hypot(cx - px, cy - py) / 1000.0,
        "inertia_cg_kg_m2": I[2, 2] * 1e-9,                       # about the CG around the pin direction (fold DOF)
        "inertia_tz_kg_m2": -I[0, 2] * 1e-9,                      # tensor entry e_t–e_z with e_t = −x at fold 0
        "axial_offset_m": d.lug_midplane_offset_mm / 1000.0,
        "chordwise_cg_offset_mm": cx - px,                        # not representable in fold_cycle v1
        "hinge_inertia_kg_m2": distal.inertia_about((px, py, cz))[2, 2] * 1e-9,
        "declaration_kind": "exploratory_assumption",
        "source": f"CAD katı modeli {d.name} + {distal.method}; basılı parça tartılınca değiştirilecek.",
    }


def properties(parts) -> dict:
    """Per part and per assembly mass properties for one blade (proximal with hub sector, distal, pin set)."""
    d = parts.design
    prox = printed(parts.proximal, d)
    dist = printed(parts.distal, d)
    hw = {k: steel(v) for k, v in parts.hardware.items()}
    pin_set = combine(list(hw.values()), "pim seti (çelik)")
    return {"proximal": prox, "distal": dist, "hardware": hw, "pin_set": pin_set,
            "blade": combine([prox, dist, pin_set], "kanat (proksimal + distal + pim seti)"),
            "fold": fold_mechanism_equivalent(dist, d)}
