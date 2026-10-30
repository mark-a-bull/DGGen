"""Pure text and date helpers, with no reportlab/faker/game-state dependencies.

Everything here is a pure function, which makes this the cheapest and highest-value module to
unit test.
"""

from __future__ import annotations

import re
from datetime import date, datetime
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Callable

# Generational suffixes, which belong after the given name rather than being taken for a surname.
# ("V" is deliberately absent: it is far more likely a middle initial.)
_SUFFIX = re.compile(r"(?:jr|sr|ii|iii|iv)\.?", re.IGNORECASE)

# Accepted --birthdate / --birth input formats, tried in order.
_DATE_FORMATS = ("%Y-%m-%d", "%B %d, %Y", "%b %d, %Y", "%m/%d/%Y")


class TemplateError(ValueError):
    """A template from a data file is malformed or names a placeholder that isn't provided."""


# `{{` / `}}` are literal braces, `{name}` is a placeholder; any other brace is an error.
_TEMPLATE_TOKEN = re.compile(r"\{\{|\}\}|\{([^\W\d]\w*)\}|[{}]")


def fill_template(template: str, **values: object) -> str:
    """Substitute `{name}` placeholders from `values`.

    Templates live in data files, which anyone can swap in (`--employer-data`,
    `--education-data`), so this deliberately supports only plain names (plus `{{`/`}}` for
    literal braces). Unlike `str.format` it cannot reach attributes or items (`{city.__class__}`,
    `{0[1]}`), apply format specs, or crash with a bare IndexError/KeyError: anything unsupported
    raises `TemplateError` saying what is wrong. Substituted values are inserted verbatim, never
    re-interpreted.
    """

    def replace(match: re.Match[str]) -> str:
        token = match.group(0)
        if token in ("{{", "}}"):
            return token[0]
        name = match.group(1)
        if name is None:
            raise TemplateError(
                f"{template!r}: unsupported or unbalanced brace; only plain {{name}} "
                "placeholders are allowed (use {{ and }} for literal braces)",
            )
        if name not in values:
            available = ", ".join(f"{{{key}}}" for key in values) or "none"
            raise TemplateError(
                f"{template!r}: unknown placeholder {{{name}}}; available: {available}",
            )
        return str(values[name])

    return _TEMPLATE_TOKEN.sub(replace, template)


def _parse_with(value: str, fmt: str) -> date | None:
    try:
        return datetime.strptime(value, fmt).date()
    except ValueError:
        return None


def parse_date(value: str) -> date:
    """Parse a date given as YYYY-MM-DD or 'Month D, YYYY'. Raises ValueError if it is neither."""
    for fmt in _DATE_FORMATS:
        if (parsed := _parse_with(value, fmt)) is not None:
            return parsed
    raise ValueError(
        f"Invalid date {value!r}. Use YYYY-MM-DD or 'Month D, YYYY', e.g. 'November 24, 1986'.",
    )


def format_name(name: str) -> str:
    """Format a name for the sheet's LAST NAME, FIRST NAME, MIDDLE INITIAL field.

    Names already containing a comma (e.g. 'SMITH, John') are assumed to already be in that
    order and are left as-is. Otherwise the name is assumed to be given in natural reading
    order (e.g. 'Dr. John Smith') and is rewritten as 'SMITH, Dr. John'.
    """
    name = " ".join(name.split())  # trim and collapse stray whitespace
    head, comma, tail = name.partition(",")
    if comma and not _SUFFIX.fullmatch(tail.strip()):
        return f"{head.strip()}, {tail.strip()}"
    if comma:  # "John Smith, Jr." - a suffix after a comma, not a "SURNAME, Given" name
        name = f"{head.strip()} {tail.strip()}"
    words = name.split(" ")
    suffix = words.pop() if len(words) > 1 and _SUFFIX.fullmatch(words[-1]) else ""
    given, _, surname = " ".join(words).rpartition(" ")
    if not given:
        return " ".join(filter(None, [surname.upper(), suffix]))
    return f"{surname.upper()}, {' '.join(filter(None, [given, suffix]))}"


def age_on(birthdate: date, today: date) -> int:
    """Whole years from `birthdate` to `today`, accounting for whether the birthday has passed."""
    return (
        today.year - birthdate.year - ((today.month, today.day) < (birthdate.month, birthdate.day))
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
