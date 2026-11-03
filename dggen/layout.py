"""Where each field is drawn on the character sheet, loaded from `dggen/data/sheet-layout.json`.

The coordinates used to be a 200-line dict inside `pdf.py`. They are data: every one is a point on
the background image, and a different sheet design (or a language variant) is a different file,
not a code change. This module is reportlab-free so the data layer can check against it.

Coordinates are in points (1/72 inch) with the origin at the bottom-left of the page.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from dggen import config
from dggen.errors import DataError

if TYPE_CHECKING:
    from pathlib import Path


@dataclass(frozen=True)
class SheetLayout:
    """`fields` maps a field name to `(x, y, font_size)`; `max_widths` maps the single-line
    fields that must be shrunk to fit (see `text.shrink_to_fit`) to the width they may occupy."""

    fields: dict[str, tuple[int, int, int]]
    max_widths: dict[str, float]


def load_layout(path: Path | None = None) -> SheetLayout:
    """Read and check a layout file (default: the bundled one). Raises `DataError` naming the
    file and the problem; nothing here fails later, at draw time."""
    path = path or config.DEFAULT_SHEET_LAYOUT
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise DataError(f"{path}: not valid JSON ({exc})") from exc

    def fail(message: str) -> DataError:
        return DataError(f"{path}: {message}")

    if not isinstance(raw, dict) or not isinstance(raw.get("fields"), dict):
        raise fail("expected an object with a 'fields' object of groups")

    fields: dict[str, tuple[int, int, int]] = {}
    seen_in: dict[str, str] = {}
    for group, entries in raw["fields"].items():
        for name, value in entries.items():
            if not (
                isinstance(value, list)
                and len(value) == 3
                and all(isinstance(n, int | float) and not isinstance(n, bool) for n in value)
            ):
                raise fail(f"field {name!r} in {group!r} must be [x, y, font_size] (numbers)")
            if name in seen_in:
                raise fail(f"field {name!r} appears twice (in {seen_in[name]!r} and {group!r})")
            seen_in[name] = group
            fields[name] = (int(value[0]), int(value[1]), int(value[2]))

    max_widths: dict[str, float] = {}
    for name, width in _mapping(raw, "max_widths", fail).items():
        if name not in fields:
            raise fail(f"max_widths names {name!r}, which is not a field")
        max_widths[name] = width

    _add_weapon_name_widths(raw, fields, max_widths, fail)
    return SheetLayout(fields=fields, max_widths=max_widths)


def _mapping(raw: dict[str, Any], key: str, fail: Any) -> dict[str, float]:
    value = raw.get(key, {})
    if not isinstance(value, dict):
        raise fail(f"'{key}' must be an object")
    return value


def _add_weapon_name_widths(
    raw: dict[str, Any],
    fields: dict[str, tuple[int, int, int]],
    max_widths: dict[str, float],
    fail: Any,
) -> None:
    """Weapon names are drawn in full and shrunk to the gap before the 'roll' column (minus a
    little air) rather than truncated, which made distinct weapons look identical."""
    gap = raw.get("weapon_name_gap", 4)
    for slot in range(raw.get("weapon_slots", 0)):
        name, roll = f"weapon{slot}", f"weapon{slot}_roll"
        for needed in (name, roll):
            if needed not in fields:
                raise fail(f"weapon slot {slot} needs a field {needed!r}")
        max_widths[name] = fields[roll][0] - fields[name][0] - gap
