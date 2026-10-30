"""Pure text and date helpers, with no reportlab/faker/game-state dependencies.

Everything here is a pure function, which makes this the cheapest and highest-value module to
unit test.
"""

from __future__ import annotations

import argparse
import re
from datetime import date, datetime
from typing import TYPE_CHECKING

from dggen.constants import STATS

if TYPE_CHECKING:
    from collections.abc import Callable

    from dggen.character import Character
    from dggen.equipped import EquippedWeapon
    from dggen.models import Profession

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
    """Parse a date given as YYYY-MM-DD or 'Month D, YYYY' (argparse type= callable)."""
    for fmt in _DATE_FORMATS:
        if (parsed := _parse_with(value, fmt)) is not None:
            return parsed
    raise argparse.ArgumentTypeError(
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


def _skill_rows(skills: dict[str, int], labels: dict[str, str]) -> list[tuple[str, int]]:
    """(display name, score) rows, sorted by name.

    Sub-skill names live in `labels` as `<base>label` next to their `<base>value` score in
    `skills` (e.g. `craft1label: "Electrician"`, `craft1value: 40`) because that is how the sheet
    stores them. Fold each pair into one "Craft (Electrician)" row.
    """
    rows = []
    for key, score in skills.items():
        if key.endswith("value"):
            base = key[: -len("value")]
            name = base.rstrip("0123456789").title()
            if label := labels.get(f"{base}label"):
                name += f" ({label})"
        else:
            name = key.title()
        rows.append((name, score))
    return sorted(rows)


def _identity_lines(char: Character) -> list[str]:
    lines = [
        f"{char.name} - {char.profession_label}",
        f"{'Male' if char.sex == 'male' else 'Female'}, age {char.age} "
        f"({char.birth_month_abbrev} {char.birth_day})",
    ]
    for label, value in (
        ("Employer", char.employer),
        ("Education", char.education),
        ("Nationality", char.nationality),
    ):
        if value:
            lines.append(f"{label}: {value}")
    return lines


def _stat_lines(char: Character) -> list[str]:
    lines = ["Statistics:"]
    for stat in STATS:
        score = char.stats.get(stat, 0)
        lines.append(f"  {stat.capitalize():<14} {score:3d}  (x5 {score * 5})")
    return lines


def _condition_lines(char: Character) -> list[str]:
    sanity = f"Sanity: {char.sanity}"
    if char.current_sanity is not None:
        sanity += f" (current {char.current_sanity})"
    lines = [
        f"Hit Points: {char.hitpoints}   Willpower: {char.willpower}   {sanity}",
        f"Breaking Point: {char.breaking_point}   Damage Bonus: {char.damage_bonus:+d}",
    ]
    if char.disorder:
        lines.append(f"Disorder: {char.disorder}")
    if char.adapted_to_violence or char.adapted_to_helplessness:
        lines.append(
            f"Adapted to Violence: {char.adapted_to_violence}   "
            f"Adapted to Helplessness: {char.adapted_to_helplessness}",
        )
    return lines


def _weapon_line(weapon: EquippedWeapon) -> str:
    parts = [f"{weapon.name} ({weapon.roll}%)"]
    if weapon.base_range:
        parts.append(f"range {weapon.base_range}")
    if weapon.ap is not None:
        parts.append(f"ap {weapon.ap}")
    if weapon.has_damage and weapon.damage_dice is not None and weapon.damage_die_type:
        modifier = f"{weapon.damage_modifier:+d}" if weapon.damage_modifier else ""
        parts.append(f"damage {weapon.damage_dice}D{weapon.damage_die_type}{modifier}")
    if weapon.ammo is not None:
        parts.append(f"ammo {weapon.ammo}")
    return f"  Weapon: {' '.join(parts)}"


def _equipment_lines(char: Character) -> list[str]:
    lines = ["Equipment:", *(_weapon_line(weapon) for weapon in char.weapons)]
    for gear in char.gear_lines:
        # Continuation lines from equipment.py's wrap(..., subsequent_indent="  ") - merge back
        # onto the previous entry instead of prefixing "Gear:" again.
        if gear.startswith("  ") and lines[-1].startswith("  Gear:"):
            lines[-1] += " " + gear.strip()
        else:
            lines.append(f"  Gear: {gear}")
    return lines


def format_details(char: Character) -> str:
    """Render a generated character's structured state as a readable multi-line summary.

    Reads `Character`'s own fields directly rather than the sheet-keyed `d`/`e` dicts from
    `dggen.serialize`, since those are formatted for the PDF layer (checkbox marks, `_x5`
    suffixes, "DB=%d" strings) rather than for reading as plain text.
    """
    sections = [
        _identity_lines(char),
        _stat_lines(char),
        _condition_lines(char),
        [
            "Skills:",
            *(
                f"  {name:<26} {score}%"
                for name, score in _skill_rows(char.skills, char.skill_labels)
            ),
        ],
    ]
    if char.bonds:
        sections.append(
            ["Bonds:", *(f"  Bond {i + 1}: {score}" for i, score in char.bonds.items())]
        )
    if char.weapons or char.gear_lines:
        sections.append(_equipment_lines(char))
    lines: list[str] = []
    for section in sections:
        if lines:
            lines.append("")  # blank line between sections
        lines.extend(section)
    return "\n".join(lines)
