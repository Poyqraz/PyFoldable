"""Blade geometry specs for the 3-D views, built from the object being shown (never from current inputs).

* the active design (design tab),
* a saved research result (its retained draft TOML, checksum-verified),
* a coupled record (its case geometry; profile coordinates re-read from the catalog and checked against the
  record's coordinate sha256; fails closed on a mismatch).
"""
from __future__ import annotations

import hashlib
import math

from pyfoldable.core.airfoil import airfoil_coordinate_sha256
from pyfoldable.core.config import tomllib
from pyfoldable.core.profile_catalog import load_project_airfoil
from pyfoldable.visualization import blade_surface as bs


def spec_from_active(active, foil) -> bs.BladeSpec:
    return bs.spec_from_design(active, foil)


def spec_from_saved_research(row) -> bs.BladeSpec:
    from . import design_analysis
    from .design_analysis import DesignDraftArtifact
    text = row["draft_toml"]
    if row["draft_sha256"] != hashlib.sha256(text.encode()).hexdigest():
        raise ValueError("Saved draft checksum mismatch.")
    source = tomllib.loads(text)["metadata"]["source_design_sha256"]
    design, _ = design_analysis._load_geometry(DesignDraftArtifact("saved.toml", text, source, row["draft_sha256"]))
    bs.require_default_hinge(design.hinge)
    profile = row["inputs"]["profile"]
    foil = next(f for f in design.airfoils if f.id == profile)
    root_mm = row["inputs"].get("root_mm")
    R = design.blade.radius_m
    return bs.BladeSpec(foil.id, tuple(tuple(map(float, p)) for p in foil.coordinates),
                        tuple((s.r_over_R * R, s.chord_m, s.twist_rad) for s in design.blade.stations),
                        design.blade.hub_radius_m, None if root_mm is None else root_mm / 1000.0, design.hinge.radius_m,
                        R, design.blade.blade_count)


def spec_from_coupled(row) -> bs.BladeSpec:
    g = row["run_definition"]["case"]["geometry"]
    research = row["request"]["research"]
    foil = load_project_airfoil(g["profile"])
    if airfoil_coordinate_sha256(foil) != research["coordinate_sha256"]:
        raise ValueError("Catalog profile coordinates differ from the record's coordinate sha256.")
    stations = sorted({(round(s["radius_m"], 12), s["chord_m"], s["twist_rad"])
                       for s in g["proximal_sections"] + g["distal_sections"] if s.get("source") == "station"})
    return bs.BladeSpec(foil.id, tuple(tuple(map(float, p)) for p in foil.coordinates), tuple(stations),
                        g["hub_radius_m"], g.get("root_radius_m"), g["hinge_radius_m"], g["tip_radius_m"],
                        g["blade_count"])


def _window_row(row, window, key):
    s = next((r for r in row["series"] if r["window"] == window), None)
    if s is None:
        raise KeyError(window)
    return s[key]


def _state(row, window):
    entry = next((e for e in row["node_states"] if e["window"] == window), None)
    if entry is None:
        raise KeyError(window)
    return entry


def _bodies(row):
    """Body nodes: ``run_definition["bodies"]``, or the body coupling nodes of earlier split_rigid records."""
    rd = row["run_definition"]
    items = rd.get("bodies") or [n for n in rd["coupling_nodes"] if n["mbdyn_label"] < 1000]
    return {(b["blade"], b["segment"]): b for b in items}


def folds_deg(row, window: int) -> list:
    return list(_window_row(row, window, "theta_deg"))


def node_transforms(row, window: int) -> list:
    """Per blade: f(points_body_m, moving_mask) -> world [m] from the accepted MBDyn body states of ``window``
    (world = x_node + R_node (p - local_node); proximal or distal body by the mask)."""
    import numpy as np
    from pyfoldable.coupled.frames import rotvec_to_matrix
    entry = _state(row, window)
    bodies = _bodies(row)
    out = []
    for blade in range(row["run_definition"]["case"]["geometry"]["blade_count"]):
        pose = {}
        for seg in ("proximal", "distal"):
            body = bodies[(blade, seg)]
            st = entry["nodes"][str(body["mbdyn_label"])]
            pose[seg] = (np.asarray(st["x"], float), np.asarray(rotvec_to_matrix(st["phi"]), float),
                         np.asarray(body["local"], float))

        def transform(p, moving, pose=pose):
            p = np.asarray(p, float)
            out_p = np.empty_like(p)
            for seg, sel in (("proximal", ~np.asarray(moving, bool)), ("distal", np.asarray(moving, bool))):
                x, R, local = pose[seg]
                out_p[sel] = x + (p[sel] - local) @ R.T
            return out_p
        out.append(transform)
    return out


def rotor_azimuth(row, window: int) -> float:
    """Shaft azimuth at the accepted window from the orientation of blade 1's proximal body (no fold in it)."""
    from pyfoldable.coupled.frames import rotvec_to_matrix
    body = _bodies(row)[(0, "proximal")]
    R = rotvec_to_matrix(_state(row, window)["nodes"][str(body["mbdyn_label"])]["phi"])
    return math.atan2(R[1][0], R[0][0])
