"""Dependency-light rendering helpers for the engineering workspace."""

from __future__ import annotations


def _markdown_cell(value: object) -> str:
    if value is None:
        return ""
    if isinstance(value, float):
        text = f"{value:.6g}"
    else:
        text = str(value)
    return (
        text.replace("\r\n", "\n")
        .replace("\r", "\n")
        .replace("|", "\\|")
        .replace("\n", "<br>")
    )


def build_markdown_table(rows: list[dict[str, object]]) -> str:
    """Build a small read-only table without Pandas or Arrow conversion."""
    if not rows:
        return ""
    headers = tuple(rows[0])
    if any(tuple(row) != headers for row in rows):
        raise ValueError("Table rows must use one ordered column schema.")
    header = "| " + " | ".join(_markdown_cell(item) for item in headers) + " |"
    separator = "| " + " | ".join("---" for _ in headers) + " |"
    body = [
        "| " + " | ".join(_markdown_cell(row[column]) for column in headers) + " |"
        for row in rows
    ]
    return "\n".join((header, separator, *body))
