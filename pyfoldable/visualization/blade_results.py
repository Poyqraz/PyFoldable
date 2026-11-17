"""Analysis results as spanwise strips on the lofted blade (BEM annuli, coupled lifting-line elements).

A sectional result belongs to a radial interval, not to a chordwise position: each strip carries one
value across the whole chord of its interval. Three kinds are kept apart:

* ``per_span``: load per unit span (BEM dT/dr; coupled element force divided by the element width),
* ``element_total``: load integrated over the element's span (BEM annulus thrust; coupled element force),
* ``section_state``: the section's operating state (alpha, cl, cd, Re, Mach, ...).

None of them is a chordwise pressure distribution; surfaces without analysis data stay uncoloured (NaN).
"""
from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np

STRIP_NOTE = ("Bir kesit değeri şeridin tüm kirişine tek renk olarak yayılır; kordal basınç dağılımı değildir.")


@dataclass(frozen=True)
class Field:
    key: str
    label: str
    unit: str
    kind: str                            # per_span | element_total | section_state
    strips: tuple                        # ((r_in, r_out, value), ...) ascending
    note: str = ""
    source: str = ""
    approximate_widths: bool = False     # coupled per-span values from midpoint widths (layout not reproduced)


_KIND_NOTE = {
    "per_span": "Birim açıklık başına yük. " + STRIP_NOTE,
    "element_total": "Eleman toplamı: elemanın açıklığı boyunca entegre yük (eleman genişliğine bağlıdır). " + STRIP_NOTE,
    "section_state": "Kesit durumu (hesaplanan). " + STRIP_NOTE,
}


def _field(key, label, unit, kind, strips, source, approximate=False):
    note = _KIND_NOTE[kind] + (" Eleman genişlikleri yaklaşık (kaydın eleman düzeni yeniden üretilemedi; orta "
                               "nokta sınırları)." if approximate else "")
    return Field(key, label, unit, kind, tuple((float(a), float(b), float(v)) for a, b, v in strips), note, source,
                 approximate)


def bem_fields(result_row) -> dict:
    """Fields of a saved research BEM result (fully deployed rotor, fold 0)."""
    els = result_row["aerodynamics"]["radial_elements"]
    iv = [(e["inner_radius_m"], e["outer_radius_m"]) for e in els]
    sol = [e["solution"] for e in els]

    def strips(values):
        return [(a, b, v) for (a, b), v in zip(iv, values)]
    src = "BEM (saklanan sonuç)"
    out = [
        _field("dthrust_per_span", "İtki / birim yarıçap dT/dr", "N/m", "per_span", strips(s["differential_thrust_n_m"] for s in sol), src),
        _field("dtorque_per_span", "Tork / birim yarıçap dQ/dr", "N·m/m", "per_span", strips(s["differential_torque_nm_m"] for s in sol), src),
        _field("thrust_element", "Halka itkisi (eleman toplamı)", "N", "element_total", strips(e["thrust_n"] for e in els), src),
        _field("torque_element", "Halka torku (eleman toplamı)", "N·m", "element_total", strips(e["torque_nm"] for e in els), src),
        _field("alpha", "Hücum açısı α", "°", "section_state", strips(math.degrees(s["angle_of_attack_rad"]) for s in sol), src),
        _field("cl", "Taşıma katsayısı cl", "-", "section_state", strips(s["cl"] for s in sol), src),
        _field("cd", "Sürükleme katsayısı cd", "-", "section_state", strips(s["cd"] for s in sol), src),
        _field("reynolds", "Reynolds sayısı", "-", "section_state", strips(s["reynolds"] for s in sol), src),
        _field("mach", "Mach sayısı", "-", "section_state", strips(s["mach"] for s in sol), src),
    ]
    if all("axial_induced_velocity_m_s" in s for s in sol):
        out.append(_field("induced_axial", "Eksenel indüklenmiş hız", "m/s", "section_state",
                          strips(s["axial_induced_velocity_m_s"] for s in sol), src))
    return {f.key: f for f in out}


def _layout(row):
    """Element intervals as the deck builds them (``coupled.deck._allocate_elements``): one continuous line over
    the station intervals with 2 x elements_per_segment (continuous_rbf), or each segment's sections with
    elements_per_segment (split_rigid); uniform within each interval."""
    from types import SimpleNamespace
    from pyfoldable.coupled import deck
    case = row["run_definition"]["case"]
    g, eps = case["geometry"], case["controls"]["elements_per_segment"]
    if case["controls"].get("aero_topology", "split_rigid") == "continuous_rbf":
        radii = sorted({s["radius_m"] for s in g["proximal_sections"] + g["distal_sections"] if s["source"] == "station"})
        groups = [(radii, 2 * eps)]
    else:
        groups = [([s["radius_m"] for s in g[k]], eps) for k in ("proximal_sections", "distal_sections")]
    bounds = []
    for radii, total in groups:
        counts = deck._allocate_elements(tuple(SimpleNamespace(radius_m=r) for r in radii), total)
        for (a, b), n in zip(zip(radii, radii[1:]), counts):
            bounds += [(a + k * (b - a) / n, a + (k + 1) * (b - a) / n) for k in range(n)]
    return bounds


def element_layout(row) -> tuple[list, bool]:
    """(intervals, approximate): the deck layout when it reproduces the recorded element centres, otherwise
    midpoint intervals flagged as approximate."""
    ix = {c: i for i, c in enumerate(row["radial_columns"])}
    w0 = row["radial"][0][ix["window"]]
    mids = sorted(r[ix["span_y_m"]] for r in row["radial"] if r[ix["window"]] == w0 and r[ix["blade"]] == 0)
    try:
        bounds = _layout(row)
    except (KeyError, ValueError, ZeroDivisionError):
        bounds = []
    if len(bounds) == len(mids) and all(abs(0.5 * (p + q) - m) <= 2e-4 for (p, q), m in zip(bounds, mids)):
        return bounds, False
    edges = [mids[0] - 0.5 * (mids[1] - mids[0])] + [0.5 * (p + q) for p, q in zip(mids, mids[1:])] \
        + [mids[-1] + 0.5 * (mids[-1] - mids[-2])]
    return list(zip(edges, edges[1:])), True


def element_bounds(row) -> list:
    return element_layout(row)[0]


def coupled_fields(row, window: int, blade: int = 0) -> dict:
    """Fields of one accepted window of a coupled record for one blade (element forces are global, N)."""
    ix = {c: i for i, c in enumerate(row["radial_columns"])}
    rows = sorted((r for r in row["radial"] if r[ix["window"]] == window and r[ix["blade"]] == blade),
                  key=lambda r: r[ix["span_y_m"]])
    bounds, approx = element_layout(row)
    if len(rows) != len(bounds):
        raise ValueError("Element count of this window differs from the record's element layout.")

    def strips(col, scale=None):
        return [(a, b, r[ix[col]] * (1.0 if scale is None else scale(a, b))) for (a, b), r in zip(bounds, rows)]
    src = f"DUST kaldırma çizgisi · pencere {window} · kanat {blade + 1}"
    out = [
        _field("fz_element", "Eksenel kuvvet dF_z (eleman toplamı, itki yönü)", "N", "element_total", strips("dFz_n"), src),
        _field("fz_per_span", "Eksenel kuvvet / birim açıklık", "N/m", "per_span", strips("dFz_n", lambda a, b: 1.0 / (b - a)),
               src, approx),
        _field("alpha", "Hücum açısı α", "°", "section_state", strips("alpha_deg"), src),
        _field("cl", "Taşıma katsayısı cl", "-", "section_state", strips("cl"), src),
        _field("cd", "Sürükleme katsayısı cd", "-", "section_state", strips("cd"), src),
        _field("reynolds", "Reynolds sayısı", "-", "section_state", strips("reynolds"), src),
        _field("mach", "Mach sayısı", "-", "section_state", strips("mach"), src),
    ]
    return {f.key: f for f in out}


def coupled_range(row, key: str) -> tuple[float, float]:
    """Colour limits fixed over every accepted window and blade of the valid prefix."""
    ix = {c: i for i, c in enumerate(row["radial_columns"])}
    valid = row["execution"]["valid_prefix_windows"]
    windows = sorted({r[ix["window"]] for r in row["radial"] if r[ix["window"]] <= valid})
    blades = sorted({r[ix["blade"]] for r in row["radial"]})
    vals = [s[2] for w in windows for b in blades for s in coupled_fields(row, w, b)[key].strips]
    return (min(vals), max(vals))


def face_values(mesh, field: Field) -> np.ndarray:
    """Per-face value: side faces of the analysed surface take their strip's value; caps, joint cuts and
    placeholders (no data) stay NaN."""
    vals = np.full(len(mesh.faces), np.nan)
    side = np.isin(mesh.surface, ("upper", "lower", "te_face")) & np.isin(mesh.region, ("aero", "joint"))
    starts = np.array([s[0] for s in field.strips])
    ends = np.array([s[1] for s in field.strips])
    values = np.array([s[2] for s in field.strips])
    r = mesh.face_radius
    k = np.clip(np.searchsorted(starts, r, side="right") - 1, 0, len(values) - 1)
    ok = side & (r >= starts[k] - 1e-12) & (r <= ends[k] + 1e-12)       # faces in a gap between strips stay NaN
    vals[ok] = values[k[ok]]
    return vals
