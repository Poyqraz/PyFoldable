"""Convert admitted retained-provider polar tables to DUST's C81 lifting-line table.

Semantics preserved (verified against DUST 3b1d2e61 src/io/mod_c81.f90):

* one block per Reynolds number, ascending (DUST rejects non-increasing Re);
* inside a block: Cl, Cd, Cm tables, rows = angle of attack in degrees,
  columns = Mach number; DUST interpolates bilinearly in (alpha, Mach);
* Cm is the quarter-chord pitching moment (XFOIL convention), consistent with
  DUST's lifting line located on the quarter-chord line;
* DUST *aborts* when alpha or Mach leaves the table span, but *linearly
  extrapolates* in Reynolds number outside [Re_min, Re_max]. Reynolds coverage
  is therefore audited after every accepted coupled step by PyFoldable.

No point is added, removed, smoothed, clamped or re-gridded. The written text
uses ``repr`` of the admitted floats so the round trip is exact.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import math
from typing import Iterable, Mapping, Sequence


@dataclass(frozen=True)
class C81Table:
    profile: str
    text: str
    sha256: str
    alpha_deg: tuple[float, ...]
    mach: tuple[float, ...]
    reynolds: tuple[float, ...]
    source_table_sha256: tuple[str, ...]

    @property
    def envelope(self) -> dict:
        return {"alpha_deg": [self.alpha_deg[0], self.alpha_deg[-1]],
                "mach": [self.mach[0], self.mach[-1]],
                "reynolds": [self.reynolds[0], self.reynolds[-1]],
                "alpha_mach_outside": "dust_aborts",
                "reynolds_outside": "dust_linear_extrapolation_audited_by_pyfoldable"}


def _sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _table_digest(table: Mapping) -> str:
    keys = ("airfoil_id", "reynolds", "mach", "alpha_rad", "cl", "cd", "cm")
    return _sha(repr(tuple((k, tuple(table[k]) if isinstance(table[k], (list, tuple)) else table[k]) for k in keys)))


def build_c81(tables: Iterable[Mapping], *, label: str | None = None) -> C81Table:
    """Build the table from admitted PolarTable mappings (as stored in admissions)."""
    rows = [dict(t) for t in tables]
    if not rows:
        raise ValueError("No admitted tables.")
    profiles = {t["airfoil_id"] for t in rows}
    if len(profiles) != 1:
        raise ValueError("C81 conversion requires a single profile.")
    profile = profiles.pop()
    alpha_sets = {tuple(t["alpha_rad"]) for t in rows}
    if len(alpha_sets) != 1:
        raise ValueError("Admitted tables do not share one angle grid; no re-gridding is performed.")
    alpha_rad = alpha_sets.pop()
    if any(b <= a for a, b in zip(alpha_rad, alpha_rad[1:])) or len(alpha_rad) < 2:
        raise ValueError("Angles must be strictly increasing with at least two points.")
    machs = sorted({float(t["mach"]) for t in rows})
    res = sorted({float(t["reynolds"]) for t in rows})
    cells = {(float(t["reynolds"]), float(t["mach"])): t for t in rows}
    if len(cells) != len(rows) or len(cells) != len(machs) * len(res):
        raise ValueError("Admitted tables are not a complete rectangular Reynolds x Mach grid.")
    if len(machs) < 2:
        raise ValueError("DUST bilinear interpolation needs at least two Mach columns.")
    n_alpha, n_mach = len(alpha_rad), len(machs)
    if n_alpha > 99 or n_mach > 99:
        raise ValueError("DUST C81 header uses I2 counts (<= 99).")
    for t in rows:
        for key in ("cl", "cd", "cm"):
            if len(t[key]) != n_alpha or not all(math.isfinite(v) for v in t[key]):
                raise ValueError(f"Non-finite or incomplete {key} in an admitted table.")
    alpha_deg = tuple(math.degrees(a) for a in alpha_rad)
    tag = (label or profile).replace(" ", "_")[:28]
    counts = f"{n_mach:02d}{n_alpha:02d}" * 3
    lines = [f"{len(res)} 0 0", "0 1", "0.158 0.158"]
    for re_value in res:
        lines += ["COMMENT#1", f"{re_value!r} 0.000", f"{tag:<30s}{counts}"]
        for key in ("cl", "cd", "cm"):
            lines.append(" ".join(repr(m) for m in machs))
            for i, a in enumerate(alpha_deg):
                lines.append(" ".join([repr(a)] + [repr(float(cells[(re_value, m)][key][i])) for m in machs]))
    text = "\n".join(lines) + "\n"
    digests = tuple(_table_digest(cells[(r, m)]) for r in res for m in machs)
    return C81Table(profile, text, _sha(text), alpha_deg, tuple(machs), tuple(res), digests)


def parse_c81(text: str) -> dict:
    """Minimal reader mirroring DUST's list-directed read (used by tests/restoration)."""
    lines = [ln for ln in text.splitlines()]
    n_re = int(lines[0].split()[0])
    pos, blocks = 3, []
    for _ in range(n_re):
        pos += 1  # COMMENT#1
        re_value = float(lines[pos].split()[0]); pos += 1
        header = lines[pos]; pos += 1
        counts = header[header.index(" "):].strip()
        ints = [int(counts[i:i + 2]) for i in range(0, 12, 2)]
        coeffs = []
        for c in range(3):
            n_mach, n_alpha = ints[2 * c], ints[2 * c + 1]
            mach = [float(v) for v in lines[pos].split()]; pos += 1
            if len(mach) != n_mach:
                raise ValueError("Mach count mismatch")
            alpha, values = [], []
            for _ in range(n_alpha):
                parts = [float(v) for v in lines[pos].split()]; pos += 1
                alpha.append(parts[0]); values.append(parts[1:])
            coeffs.append({"mach": mach, "alpha": alpha, "values": values})
        blocks.append({"reynolds": re_value, "coeffs": coeffs})
    return {"blocks": blocks}


def dust_interpolate(parsed: dict, alpha_deg: float, mach: float, reynolds: float) -> tuple[float, float, float]:
    """Re-implementation of DUST interp_aero_coeff (no Reynolds corrections).

    Raises ValueError where DUST stops with an error (alpha/Mach outside span).
    Reynolds outside the span is linearly extrapolated exactly as DUST does.
    """
    alpha = -math.floor((alpha_deg + 180.0) / 360.0) * 360.0 + alpha_deg
    blocks = parsed["blocks"]

    def interp2(block):
        out = []
        for coeff in block["coeffs"]:
            a, m, v = coeff["alpha"], coeff["mach"], coeff["values"]
            if not a[0] <= alpha <= a[-1]:
                raise ValueError(f"alpha {alpha} outside table span {a[0]}..{a[-1]}")
            if not m[0] <= mach <= m[-1]:
                raise ValueError(f"Mach {mach} outside table span {m[0]}..{m[-1]}")
            i1 = next(i for i in range(len(a)) if a[i] > alpha) if alpha < a[-1] else len(a) - 1
            i2 = next(i for i in range(len(m)) if m[i] > mach) if mach < m[-1] else len(m) - 1
            c1 = 2.0 * (alpha - 0.5 * (a[i1 - 1] + a[i1])) / (a[i1] - a[i1 - 1])
            c2 = 2.0 * (mach - 0.5 * (m[i2 - 1] + m[i2])) / (m[i2] - m[i2 - 1])
            p1, p2 = .25 * (1 + c1) * (1 + c2), .25 * (1 - c1) * (1 + c2)
            p3, p4 = .25 * (1 - c1) * (1 - c2), .25 * (1 + c1) * (1 - c2)
            out.append(p1 * v[i1][i2] + p2 * v[i1 - 1][i2] + p3 * v[i1 - 1][i2 - 1] + p4 * v[i1][i2 - 1])
        return out

    if len(blocks) == 1:
        return tuple(interp2(blocks[0]))  # type: ignore[return-value]
    res = [b["reynolds"] for b in blocks]
    if reynolds < res[0]:
        k = 0
    elif reynolds > res[-1]:
        k = len(res) - 2
    else:
        k = max(i for i in range(len(res) - 1) if res[i] <= reynolds) if reynolds < res[-1] else len(res) - 2
    lo, hi = interp2(blocks[k]), interp2(blocks[k + 1])
    r1, r2 = res[k], res[k + 1]
    return tuple((a * (r2 - reynolds) + b * (reynolds - r1)) / (r2 - r1) for a, b in zip(lo, hi))  # type: ignore[return-value]


def admitted_tables(admission: Mapping) -> list[dict]:
    """Rebuild PolarTable mappings from a provider admission without any solve."""
    from dataclasses import asdict
    from pyfoldable.application import provider_design_analysis as managed

    if admission.get("complete_family_admitted") is not True:
        raise ValueError("Only a complete admitted family can supply a DUST table.")
    tables = []
    for cell in admission["cells"]:
        if cell.get("status") != "admitted":
            raise ValueError("A non-admitted cell cannot enter a DUST table.")
        table = asdict(managed._result(cell["returned_document"]).to_polar_table(require_complete=True))
        tables.append({k: table[k] for k in ("airfoil_id", "reynolds", "mach", "alpha_rad", "cl", "cd", "cm")})
    return tables


def tables_summary(tables: Sequence[Mapping]) -> list[dict]:
    return [{k: (list(t[k]) if isinstance(t[k], (list, tuple)) else t[k])
             for k in ("airfoil_id", "reynolds", "mach", "alpha_rad", "cl", "cd", "cm")} for t in tables]
