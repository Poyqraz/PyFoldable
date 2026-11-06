"""Pure, bounded consistency assessment of retained XFOIL polar headers.

MIT xfoil6.99.tgz sha256:5c0250643f52ce0e75d7338ae2504ce7907f2d49a30f921826717b8ac12ebe40
Xfoil/src/iopol.f sha256:7ab33bdac69a0cc620a4d2de18f85e75f50846337443762ed82bfa7012356e7e
POLWRIT lines515/560/684/692: input NAME, MACH1 F7.3, REYN1/1e6 F9.3.
No solver, build, adapter modification or process-image attestation occurs here.
"""
from __future__ import annotations

from fractions import Fraction
import re

from pyfoldable.core.providers import PolarGenerationRequest


_LABEL = re.compile(r"\b(Mach|Re|Ncrit)\b\s*(=|:|(?=[+\-\d*]))", re.IGNORECASE)
_FIXED = r"[+-]?\d+\.\d{3}"


def _decimal_text(value: Fraction) -> str:
    """Exact terminating decimal for the binary/decimal rationals used here."""
    whole, remainder = divmod(abs(value.numerator), value.denominator)
    digits = []
    while remainder:
        digit, remainder = divmod(remainder * 10, value.denominator)
        digits.append(str(digit))
    return ("-" if value < 0 else "") + str(whole) + (("." + "".join(digits)) if digits else "")


def assess_retained_xfoil_header(text: str, request: PolarGenerationRequest, *, script: str, airfoil_input: str) -> dict:
    """Present supported fields must agree; missing fields stay unavailable.

    Headerless records remain supported, as before this repair. Absence does not
    become observed profile/Mach/Re evidence. Recognized but malformed, duplicate
    or contradictory fields reject. Ncrit/xtrf and other header text are retained
    raw but not interpreted by this narrowly scoped profile/Mach/Re check.
    """
    header = []
    for line in text.splitlines():
        tokens = {s.casefold() for s in line.split()}
        if {"alpha", "cl", "cd", "cm"} <= tokens:
            break
        header.append(line)
    values = {"profile": [], "mach": [], "reynolds": []}
    for number, line in enumerate(header, 1):
        if re.search(r"\bCalculated\s+polar\s+for\b", line, re.IGNORECASE):
            match = re.fullmatch(r"\s*Calculated\s+polar\s+for\s*:\s*(.*?)\s*", line, re.IGNORECASE)
            values["profile"].append({"line": number, "text": line, "token": match.group(1) if match else None})
        # Ncrit terminates Re on the standard combined line, without inventing
        # an interpretation of that additional field.
        labels = list(_LABEL.finditer(line))
        for i, match in enumerate(labels):
            name = {"mach": "mach", "re": "reynolds"}.get(match.group(1).casefold())
            if name:
                end = labels[i + 1].start() if i + 1 < len(labels) else len(line)
                values[name].append({"line": number, "text": line, "token": line[match.end():end].strip() if match.group(2) == "=" else None})
        # A known field name without '=' is malformed, not silently missing.
        for marker, name in (("Mach", "mach"), ("Re", "reynolds")):
            if re.match(rf"\s*{marker}\b", line, re.IGNORECASE) and not any(m.group(1).casefold() == marker.casefold() for m in labels):
                values[name].append({"line": number, "text": line, "token": None})
    assessed = {}
    for name, declarations in values.items():
        row = {"declarations": declarations, "status": "missing", "interpreted_value": None}
        assessed[name] = row
        if not declarations:
            continue
        if len(declarations) != 1 or not declarations[0]["token"]:
            row["status"] = "malformed"
            continue
        token = declarations[0]["token"]
        if name == "profile":
            expected = airfoil_input.splitlines()[0].strip()
            row.update({"interpreted_value": token, "expected_input_label": expected,
                        "status": "compatible" if token == expected else "contradictory"})
            continue
        pattern = _FIXED if name == "mach" else rf"({_FIXED})\s*[eE]\s*\+?6"
        match = re.fullmatch(pattern, token)
        if match is None:
            row["status"] = "malformed"
            continue
        printed = Fraction(token if name == "mach" else match.group(1))
        command = "MACH" if name == "mach" else "VISC"
        command_tokens = re.findall(rf"^{command} (\S+)\s*$", script, re.MULTILINE)
        if len(command_tokens) != 1:
            raise ValueError("Reviewed script must contain exactly one Mach/Re command")
        scale = 1 if name == "mach" else 1000000
        # The checked adapter script uses .12g. Parse that command into binary64,
        # then use the writer's binary64 /1e6 for Re. Compare with the exact
        # half-quantum interval of F*.3, not a broad user-selected tolerance.
        commanded = Fraction.from_float(float(command_tokens[0]) / scale)
        half_quantum = Fraction(1, 2000)
        lower, upper = printed - half_quantum, printed + half_quantum
        row.update({
            "status": "compatible" if lower <= commanded <= upper else "contradictory",
            "interpreted_value": _decimal_text(printed * scale),
            "requested_value": request.mach if name == "mach" else request.reynolds,
            "command_token": command_tokens[0], "command_value_in_printed_scale": _decimal_text(commanded),
            "printed_scale": scale, "printed_quantum": "0.001",
            "rounding_interval_in_printed_scale": [_decimal_text(lower), _decimal_text(upper)],
            "exact_halfway_boundary": commanded in (lower, upper),
        })
    return {
        "format": "XFOIL6.99_POLWRIT_NAME_F7.3_RE_F9.3_e6",
        "header_lines": header, "fields": assessed,
        "compatible": all(v["status"] in {"missing", "compatible"} for v in assessed.values()),
        "absence_behavior": "Missing supported fields stay unavailable; they are not observed identities or values",
        "rounding_behavior": "Closed exact half-quantum bins; exact halfway ties allow either neighboring printed token",
    }
