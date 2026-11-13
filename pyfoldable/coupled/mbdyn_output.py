"""Parse MBDyn text outputs written after each converged step.

MBDyn writes its .mov/.jnt/.frc records only after a time step has converged,
so every parsed block is an accepted state. Column meanings follow the MBDyn
manual (develop 55c86cc6): .mov = label, position(3), orientation vector(3)
(default orientation: orientation vector), velocity(3), angular velocity(3);
.jnt = label, local force(3), local moment(3), global force(3), global
moment(3), joint-specific columns.
"""
from __future__ import annotations

from pathlib import Path


def _blocks(path: Path, labels_per_block: int | None = None) -> list[dict[int, list[float]]]:
    rows = []
    for line in path.read_text().splitlines():
        parts = line.split()
        if not parts:
            continue
        rows.append((int(float(parts[0])), [float(v) for v in parts[1:]]))
    if not rows:
        return []
    first = rows[0][0]
    blocks, current = [], {}
    for label, values in rows:
        if label == first and current:
            blocks.append(current)
            current = {}
        current[label] = values
    if current:
        blocks.append(current)
    if labels_per_block is not None and any(len(b) != labels_per_block for b in blocks):
        raise ValueError(f"{path.name}: inconsistent record blocks")
    return blocks


def parse_mov(path: Path) -> list[dict[int, dict]]:
    out = []
    for block in _blocks(path):
        out.append({label: {"x": v[0:3], "phi": v[3:6], "v": v[6:9], "w": v[9:12]} for label, v in block.items()})
    return out


def parse_jnt(path: Path) -> list[dict[int, dict]]:
    out = []
    for block in _blocks(path):
        out.append({label: {"f_local": v[0:3], "m_local": v[3:6], "f_global": v[6:9], "m_global": v[9:12],
                            "extra": v[12:]} for label, v in block.items()})
    return out


def parse_out(path: Path) -> list[dict]:
    """``Step Time TStep NIter ResErr SolErr SolConv Out`` records (Step 0 = initial state)."""
    steps = []
    for line in path.read_text().splitlines():
        parts = line.split()
        if len(parts) >= 9 and parts[0] == "Step":
            try:
                steps.append({"step": int(parts[1]), "time_s": float(parts[2]), "dt_s": float(parts[3]),
                              "iterations": int(parts[4]), "residual_error": float(parts[5]),
                              "solution_error": float(parts[6]), "solution_converged": int(parts[7]),
                              "output": int(parts[8])})
            except ValueError:
                continue
    return steps
