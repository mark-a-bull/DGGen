"""Pure text and date helpers, with no reportlab/faker/game-state dependencies.

Everything here is a pure function, which makes this the cheapest and highest-value module to
unit test.
"""

from __future__ import annotations

import argparse
from datetime import date, datetime
from typing import TYPE_CHECKING, Callable

if TYPE_CHECKING:
    from dggen.models import Profession

# Accepted --birthdate / --birth input formats, tried in order.
_DATE_FORMATS = ("%Y-%m-%d", "%B %d, %Y", "%b %d, %Y", "%m/%d/%Y")


def parse_date(value: str) -> date:
    """Parse a date given as YYYY-MM-DD or 'Month D, YYYY' (argparse type= callable)."""
    for fmt in _DATE_FORMATS:
        try:
            return datetime.strptime(value, fmt).date()
        except ValueError:
            continue
    raise argparse.ArgumentTypeError(
        f"Invalid date {value!r}. Use YYYY-MM-DD or 'Month D, YYYY', e.g. 'November 24, 1986'.",
    )


def format_name(name: str) -> str:
    """Format a name for the sheet's LAST NAME, FIRST NAME, MIDDLE INITIAL field.

    Names already containing a comma (e.g. 'SMITH, John') are assumed to already be in that
    order and are left as-is. Otherwise the name is assumed to be given in natural reading
    order (e.g. 'Dr. John Smith') and is rewritten as 'SMITH, Dr. John'.
    """
    if "," in name:
        return name
    given, _, surname = name.rpartition(" ")
    if not given:
        return name.upper()
    return f"{surname.upper()}, {given}"


def age_on(birthdate: date, today: date) -> int:
    """Whole years from `birthdate` to `today`, accounting for whether the birthday has passed."""
    return (
        today.year
        - birthdate.year
        - ((today.month, today.day) < (birthdate.month, birthdate.day))
    )


def generate_label(profession: Profession) -> str:
    """Human-readable roster label: 'Label, Employer, Division' skipping blank parts."""
    return ", ".join(
        part for part in (profession.label, profession.employer, profession.division) if part
    )


def shrink_to_fit(
    text: str,
    size: int,
    max_width: float,
    measure: Callable[[str, int], float],
    min_size: int = 6,
) -> tuple[str, int]:
    """Shrink font size (down to `min_size`), then ellipsis-truncate, so `text` fits `max_width`.

    `measure(text, size)` returns the rendered width of `text` at `size`. Kept as a parameter so
    this stays reportlab-free and testable with a synthetic width function.
    """
    while size > min_size and measure(text, size) > max_width:
        size -= 1
    if measure(text, size) > max_width:
        while text and measure(text + "…", size) > max_width:
            text = text[:-1]
        text += "…"
    return text, size
