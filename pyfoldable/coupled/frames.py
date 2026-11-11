"""Finite-rotation helpers shared by deck generation and post-processing.

Conventions (see docs/coupled_dynamic_analysis.md):

* Global frame: shaft axis +Z, rotor angular velocity +Omega about +Z,
  free stream (0, 0, -V) so positive thrust is +Z.
* Blade body frame (identical to DUST's parametric lifting-line frame):
  x = chord from leading to trailing edge, y = span (outward), z = lift normal.
  Blade 1 (azimuth 0) coincides with the global frame; blade b is Rz(psi_b).
* Fold angle theta: rotation of the distal segment about the hinge axis
  (parallel to +Z) relative to the proximal segment; 0 = open, negative =
  folded back toward the trailing side, matching docs/foldable_conventions.md.
* Rotation vectors are MBDyn "orientation vector" / DUST preCICE "Rotation"
  data: R = exp([phi]x), the absolute node orientation (columns = node axes
  expressed in the global frame).
"""
from __future__ import annotations

import math
from typing import Sequence

Vec = tuple[float, float, float]
Mat = tuple[Vec, Vec, Vec]


def rot_z(angle: float) -> Mat:
    c, s = math.cos(angle), math.sin(angle)
    return ((c, -s, 0.0), (s, c, 0.0), (0.0, 0.0, 1.0))


def matmul(a: Mat, b: Mat) -> Mat:
    return tuple(tuple(sum(a[i][k] * b[k][j] for k in range(3)) for j in range(3)) for i in range(3))  # type: ignore[return-value]


def matvec(a: Mat, v: Sequence[float]) -> Vec:
    return tuple(sum(a[i][k] * v[k] for k in range(3)) for i in range(3))  # type: ignore[return-value]


def transpose(a: Mat) -> Mat:
    return tuple(tuple(a[j][i] for j in range(3)) for i in range(3))  # type: ignore[return-value]


def cross(a: Sequence[float], b: Sequence[float]) -> Vec:
    return (a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0])


def dot(a: Sequence[float], b: Sequence[float]) -> float:
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def rotvec_to_matrix(phi: Sequence[float]) -> Mat:
    """Rodrigues formula, identical in meaning to DUST mod_precice update_elems."""
    theta = math.sqrt(dot(phi, phi))
    if theta < 1e-12:
        # second-order expansion keeps the near-identity map smooth
        x, y, z = phi
        return ((1.0, -z, y), (z, 1.0, -x), (-y, x, 1.0))
    n = tuple(p / theta for p in phi)
    c, s, v = math.cos(theta), math.sin(theta), 1.0 - math.cos(theta)
    x, y, z = n
    return ((c + x * x * v, x * y * v - z * s, x * z * v + y * s),
            (y * x * v + z * s, c + y * y * v, y * z * v - x * s),
            (z * x * v - y * s, z * y * v + x * s, c + z * z * v))


def matrix_to_rotvec(r: Mat) -> Vec:
    """Inverse of :func:`rotvec_to_matrix` for |theta| < pi."""
    trace = r[0][0] + r[1][1] + r[2][2]
    cos_t = max(-1.0, min(1.0, (trace - 1.0) / 2.0))
    theta = math.acos(cos_t)
    w = (r[2][1] - r[1][2], r[0][2] - r[2][0], r[1][0] - r[0][1])
    if theta < 1e-12:
        return (w[0] / 2.0, w[1] / 2.0, w[2] / 2.0)
    if math.pi - theta < 1e-6:
        raise ValueError("Rotation of pi is not representable without ambiguity.")
    k = theta / (2.0 * math.sin(theta))
    return (k * w[0], k * w[1], k * w[2])


def relative_angle_about_z(r_parent: Mat, r_child: Mat) -> float:
    """Signed rotation of child relative to parent about the parent z axis."""
    rel = matmul(transpose(r_parent), r_child)
    return math.atan2(rel[1][0], rel[0][0])


def blade_frame(blade_index: int, blade_count: int) -> Mat:
    return rot_z(2.0 * math.pi * blade_index / blade_count)


def fmt_matrix_rowwise(r: Mat) -> str:
    return ", ".join(repr(float(v)) for row in r for v in row)
