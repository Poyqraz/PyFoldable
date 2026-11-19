"""2-D plane-stress finite-element estimate of the peak in-plane stress in a printed pin lug.

Scope: linear elastic, isotropic, plane stress in the lug plane, 9-node Lagrange quadrilaterals (Q9) with 3 x 3 Gauss
integration and scipy.sparse assembly. Units: mm, N, MPa. The pin load enters as a frictionless cosine bearing
pressure on the loaded half of the hole; the neck end is clamped. The result is a plane-stress FE result for the
in-plane pin pull only. It does not model pin contact or clearance, out-of-plane eccentric bending (handled
analytically elsewhere), FFF anisotropy, layer bonding, plasticity, creep or fatigue, and it does not qualify a part.

Geometry (lug frame): hole centre at (0, 0), boss disk of radius R, straight neck of width 2R from y = 0 to
y = -neck_length (body side, clamped). The pin pulls toward +y, away from the body. The mesh is mapped along rays
from the hole centre to a star-shaped outer boundary (boss arc for y >= 0, neck sides and clamp line below), with
geometric radial growth so that elements stay near-square around the hole.
"""
from __future__ import annotations

import math

import numpy as np
from scipy.sparse import coo_matrix
from scipy.sparse.linalg import spsolve

SCOPE = ("Düzlem gerilme FE (2-B, doğrusal elastik, izotrop, Q9 eleman): lug düzlemi içi pim yükü (sürtünmesiz "
         "kosinüs yatak basıncı), boyun ucu ankastre; düzlem dışı eğilme, pim boşluğu/temas, baskı anizotropisi "
         "ve yorulma yok. Parça yeterliliği değildir.")

_GAUSS, _GAUSS_W = np.polynomial.legendre.leggauss(3)


def _lagrange3(s):
    """Quadratic Lagrange basis on the nodes -1, 0, 1 and its derivative, each (len(s), 3)."""
    s = np.asarray(s, float)[:, None]
    basis = np.hstack([s * (s - 1) / 2, 1 - s ** 2, s * (s + 1) / 2])
    deriv = np.hstack([s - 0.5, -2 * s, s + 0.5])
    return basis, deriv


def _q9_derivatives(points):
    """dN/d(xi, eta) of the Q9 basis N[3a + b] = L_a(xi) L_b(eta) at natural points (G, 2): (G, 9, 2)."""
    lx, dlx = _lagrange3(points[:, 0])
    ly, dly = _lagrange3(points[:, 1])
    d_xi = (dlx[:, :, None] * ly[:, None, :]).reshape(-1, 9)
    d_eta = (lx[:, :, None] * dly[:, None, :]).reshape(-1, 9)
    return np.stack([d_xi, d_eta], axis=-1)


def _q9_connectivity(n_i, n_j, periodic_j):
    """Q9 elements of a node grid with 2 n_i + 1 rows (first natural coordinate) and 2 n_j (+1 if open) columns."""
    cols_total = 2 * n_j + (0 if periodic_j else 1)
    ei, ej = np.meshgrid(np.arange(n_i), np.arange(n_j), indexing="ij")
    k = np.arange(3)
    rows = 2 * ei[..., None, None] + k[:, None]
    cols = (2 * ej[..., None, None] + k[None, :]) % cols_total
    return (rows * cols_total + cols).reshape(-1, 9)


def rectangle_mesh(length, width, n_x, n_y):
    """Q9 mesh of the rectangle [0, length] x [0, width] with n_x by n_y elements: (nodes (N, 2), elements (E, 9))."""
    x = np.linspace(0.0, length, 2 * n_x + 1)
    y = np.linspace(0.0, width, 2 * n_y + 1)
    nodes = np.stack(np.meshgrid(x, y, indexing="ij"), axis=-1).reshape(-1, 2)
    return nodes, _q9_connectivity(n_x, n_y, periodic_j=False)


def _ray_mesh(hole_radius, outer_radius, breaks, d_phi, n_r, closed):
    """Q9 mesh between the hole circle and a star-shaped boundary r = outer_radius(phi) along rays from (0, 0).

    The angular range is split at ``breaks`` (boundary corners stay on element corners) into near-uniform steps of
    about d_phi; corner radii grow geometrically from the hole, mid-side radii are the corner averages so radial
    edges stay straight. Returns nodes (row i = radial level, column j = angle), elements and the node angles.
    """
    phi = [np.linspace(p0, p1, 2 * max(1, round((p1 - p0) / d_phi)) + 1)[:-1] for p0, p1 in zip(breaks, breaks[1:])]
    phi = np.concatenate(phi if closed else phi + [np.array([breaks[-1]])])
    ratio = outer_radius(phi) / hole_radius
    corners = hole_radius * ratio[None, :] ** (np.arange(n_r + 1)[:, None] / n_r)
    radius = np.empty((2 * n_r + 1, phi.size))
    radius[::2] = corners
    radius[1::2] = (corners[:-1] + corners[1:]) / 2
    nodes = np.stack([radius * np.cos(phi), radius * np.sin(phi)], axis=-1).reshape(-1, 2)
    return nodes, _q9_connectivity(n_r, phi.size // 2, periodic_j=closed), phi


def structured_lug_mesh(boss_radius, hole_radius, neck_length, n_r, n_theta):
    """Mapped Q9 mesh of the lug: n_r elements radially, n_theta elements over the upper (boss) half of the hole.

    Returns (nodes (N, 2), elements (E, 9), boundary) where boundary["hole"] lists the hole nodes counterclockwise
    from (a, 0), alternating corner and mid-side nodes, boundary["hole_angle"] their angles (rad) and
    boundary["clamp"] the nodes on the clamp line y = -neck_length.
    """
    if not 0 < hole_radius < min(boss_radius, neck_length) or n_r < 1 or n_theta < 2:
        raise ValueError("lug mesh needs 0 < hole_radius < min(boss_radius, neck_length), n_r >= 1, n_theta >= 2")

    def outer(phi):
        s, c = np.sin(phi), np.cos(phi)
        with np.errstate(divide="ignore"):
            neck = np.minimum(boss_radius / np.abs(c), neck_length / np.abs(s))
        return np.where(s >= 0.0, boss_radius, neck)

    corner = math.atan2(neck_length, boss_radius)
    breaks = [0.0, math.pi, math.pi + corner, 2 * math.pi - corner, 2 * math.pi]
    nodes, elements, phi = _ray_mesh(hole_radius, outer, breaks, math.pi / n_theta, n_r, closed=True)
    clamp = np.flatnonzero(np.abs(nodes[:, 1] + neck_length) < 1e-9 * neck_length)
    return nodes, elements, {"hole": np.arange(phi.size), "hole_angle": phi, "clamp": clamp}


def _strain_matrices(nodes, elements, points):
    """B (E, G, 3, 18) and det J (E, G) at natural points; strain = (exx, eyy, gxy), dofs (u0, v0, u1, v1, ...)."""
    d_nat = _q9_derivatives(points)
    jac = np.einsum("gkn,ekd->egnd", d_nat, nodes[elements])
    det = np.linalg.det(jac)
    if np.any(det <= 0.0):
        raise ValueError("inverted or degenerate element")
    d_xy = np.einsum("egdn,gkn->egkd", np.linalg.inv(jac), d_nat)
    b = np.zeros(det.shape + (3, 18))
    b[..., 0, 0::2] = d_xy[..., 0]
    b[..., 1, 1::2] = d_xy[..., 1]
    b[..., 2, 0::2] = d_xy[..., 1]
    b[..., 2, 1::2] = d_xy[..., 0]
    return b, det


def solve_plane_stress(nodes, elements, E, nu, thickness, fixed_nodes, nodal_forces):
    """Linear elastic plane-stress solve on a Q9 mesh.

    fixed_nodes: node indices clamped in x and y, or an (N, 2) boolean mask of fixed displacement components
    (symmetry and roller supports). nodal_forces: (N, 2) in N. Returns a dict with ``displacement`` (N, 2) mm,
    nodal-averaged ``stress`` (N, 3) = (sxx, syy, txy) MPa evaluated at the element nodes, ``von_mises`` and
    ``max_principal`` (N,) MPa, and ``reaction`` (N, 2) N (K u - f, non-zero only at fixed components).
    """
    nodes = np.asarray(nodes, float)
    n = len(nodes)
    d_mat = E / (1 - nu ** 2) * np.array([[1.0, nu, 0.0], [nu, 1.0, 0.0], [0.0, 0.0, (1 - nu) / 2]])
    gauss = np.array([(p, q) for p in _GAUSS for q in _GAUSS])
    weight = np.outer(_GAUSS_W, _GAUSS_W).ravel()
    b, det = _strain_matrices(nodes, elements, gauss)
    k_el = np.einsum("eg,egia,ij,egjb->eab", thickness * det * weight, b, d_mat, b)
    dofs = (2 * elements[:, :, None] + np.arange(2)).reshape(-1, 18)
    rows = np.repeat(dofs, 18, axis=1)
    cols = np.tile(dofs, (1, 18))
    k = coo_matrix((k_el.ravel(), (rows.ravel(), cols.ravel())), shape=(2 * n, 2 * n)).tocsr()

    fixed = np.asarray(fixed_nodes)
    if fixed.dtype != bool:
        fixed = np.zeros((n, 2), bool)
        fixed[np.asarray(fixed_nodes, int)] = True
    free = np.flatnonzero(~fixed.ravel())
    f = np.asarray(nodal_forces, float).ravel()
    u = np.zeros(2 * n)
    u[free] = spsolve(k[free][:, free].tocsc(), f[free])

    node_points = np.array([(p, q) for p in (-1.0, 0.0, 1.0) for q in (-1.0, 0.0, 1.0)])
    b_nodes, _ = _strain_matrices(nodes, elements, node_points)
    sigma = np.einsum("ij,enjk,ek->eni", d_mat, b_nodes, u[dofs])
    count = np.bincount(elements.ravel(), minlength=n)[:, None]
    stress = np.zeros((n, 3))
    np.add.at(stress, elements.ravel(), sigma.reshape(-1, 3))
    stress /= count
    sxx, syy, txy = stress.T
    return {
        "displacement": u.reshape(-1, 2),
        "stress": stress,
        "von_mises": np.sqrt(sxx ** 2 - sxx * syy + syy ** 2 + 3 * txy ** 2),
        "max_principal": (sxx + syy) / 2 + np.hypot((sxx - syy) / 2, txy),
        "reaction": (k @ u - f).reshape(-1, 2),
    }


def edge_forces(nodes, edge_nodes, traction, thickness):
    """Consistent nodal forces (N, 2) in N of a traction (MPa) along a chain of quadratic element edges.

    edge_nodes: node indices in order corner, mid, corner, ..., corner (odd length; repeat the first index to close a
    loop). traction: (2,) uniform, or (len(edge_nodes), 2) nodal values interpolated quadratically along each edge.
    """
    chain = np.asarray(edge_nodes, int)
    if chain.size < 3 or chain.size % 2 == 0:
        raise ValueError("edge_nodes must be corner, mid, corner, ... with odd length >= 3")
    t = np.broadcast_to(np.asarray(traction, float), (chain.size, 2))
    points, weight = np.polynomial.legendre.leggauss(4)
    basis, deriv = _lagrange3(points)
    forces = np.zeros((len(nodes), 2))
    for k in range(0, chain.size - 2, 2):
        edge = chain[k:k + 3]
        length = np.linalg.norm(deriv @ nodes[edge], axis=1)
        np.add.at(forces, edge, thickness * np.einsum("g,ga,gc->ac", weight * length, basis, basis @ t[k:k + 3]))
    return forces


def pin_bearing_forces(nodes, hole_nodes, hole_angles, total_force_N, direction=(0, 1)):
    """Nodal forces (N, 2) of a frictionless cosine bearing pressure from a pin pulled along ``direction``.

    The pressure p = p0 cos(phi - phi_d) acts radially outward (no tangential component) on the half of the hole
    facing ``direction`` and is zero elsewhere; phi are the node angles about the hole centre. The radial traction is
    interpolated from the nodes, integrated consistently over the closed hole loop (hole_nodes as from
    structured_lug_mesh) and scaled so the resultant along ``direction`` equals total_force_N
    (p0 = 2F/(pi a t) up to the arc discretisation).
    """
    d = np.asarray(direction, float) / np.linalg.norm(direction)
    angles = np.asarray(hole_angles, float)
    radial = np.column_stack([np.cos(angles), np.sin(angles)])
    traction = radial * np.clip(radial @ d, 0.0, None)[:, None]
    chain = np.append(hole_nodes, hole_nodes[0])
    forces = edge_forces(nodes, chain, np.vstack([traction, traction[:1]]), 1.0)
    return forces * (total_force_N / (forces.sum(axis=0) @ d))


def lug_stress(boss_radius, hole_radius, thickness, neck_length, force_N, E=3000.0, nu=0.35, level=2):
    """Peak in-plane stress of the lug under the pin pull (plane-stress FE, see the module scope).

    level >= 1 doubles the mesh density per step (n_r = 4 * 2^(level-1) radial, n_theta = 12 * 2^(level-1)
    elements over the boss half). kt_net = peak max-principal stress / net-section nominal F/((2R - 2a) t).
    """
    if level < 1 or thickness <= 0 or force_N <= 0:
        raise ValueError("lug_stress needs level >= 1, thickness > 0 and force_N > 0")
    scale = 2 ** (int(level) - 1)
    nodes, elements, boundary = structured_lug_mesh(boss_radius, hole_radius, neck_length, 4 * scale, 12 * scale)
    forces = pin_bearing_forces(nodes, boundary["hole"], boundary["hole_angle"], force_N)
    result = solve_plane_stress(nodes, elements, E, nu, thickness, boundary["clamp"], forces)
    peak = int(np.argmax(result["von_mises"]))
    nominal = force_N / ((2 * boss_radius - 2 * hole_radius) * thickness)
    peak_principal = float(result["max_principal"].max())
    return {
        "peak_von_mises_mpa": float(result["von_mises"][peak]),
        "peak_max_principal_mpa": peak_principal,
        "peak_xy_mm": (float(nodes[peak, 0]), float(nodes[peak, 1])),
        "nominal_net_mpa": nominal,
        "kt_net": peak_principal / nominal,
        "elements": len(elements),
        "scope": SCOPE,
    }


def plate_with_hole_kt(hole_radius, width, height, n_r, n_theta):
    """Verification: Kt = sigma_max / sigma_far of a width x height plate with a central hole in uniaxial tension.

    Quarter model with symmetry supports; uniform traction along y on the far edge y = height/2; sigma_far is the
    gross far-field stress. n_theta elements per 90 degrees around the hole, n_r radially. Kt is independent of
    E and nu (traction-only plane problem), so unit values are used.
    """
    half_w, half_h = width / 2, height / 2
    if not 0 < hole_radius < min(half_w, half_h):
        raise ValueError("plate needs 0 < hole_radius < min(width, height)/2")

    def outer(phi):
        with np.errstate(divide="ignore"):
            return np.minimum(half_w / np.abs(np.cos(phi)), half_h / np.abs(np.sin(phi)))

    breaks = [0.0, math.atan2(half_h, half_w), math.pi / 2]
    nodes, elements, phi = _ray_mesh(hole_radius, outer, breaks, math.pi / 2 / n_theta, n_r, closed=False)
    tol = 1e-9 * half_h
    fixed = np.column_stack([np.abs(nodes[:, 0]) < tol, np.abs(nodes[:, 1]) < tol])
    rim = np.arange(len(nodes) - phi.size, len(nodes))
    far_edge = rim[np.abs(nodes[rim, 1] - half_h) < tol]
    forces = edge_forces(nodes, far_edge, (0.0, 1.0), 1.0)
    result = solve_plane_stress(nodes, elements, 1.0, 0.3, 1.0, fixed, forces)
    return float(result["max_principal"].max())
