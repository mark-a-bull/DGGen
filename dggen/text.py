"""Pure text and date helpers, with no reportlab/faker/game-state dependencies.

Everything here is a pure function, which makes this the cheapest and highest-value module to
unit test.
"""

from __future__ import annotations

import argparse
from datetime import date, datetime
from typing import TYPE_CHECKING, Callable

from dggen.constants import STATS

if TYPE_CHECKING:
    from dggen.character import Character
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


def format_details(char: Character) -> str:
    """Render a generated character's structured state as a readable multi-line summary.

    Reads `Character`'s own fields directly rather than the sheet-keyed `d`/`e` dicts from
    `dggen.serialize`, since those are formatted for the PDF layer (checkbox marks, `_x5`
    suffixes, "DB=%d" strings) rather than for reading as plain text.
    """
    lines = [
        f"{char.name} - {char.profession_label}",
        f"{'Male' if char.sex == 'male' else 'Female'}, age {char.age} "
        f"({char.birth_month_abbrev} {char.birth_day})",
    ]
    if char.employer:
        lines.append(f"Employer: {char.employer}")
    if char.education:
        lines.append(f"Education: {char.education}")
    if char.nationality:
        lines.append(f"Nationality: {char.nationality}")

    lines.append("")
    lines.append("Statistics:")
    for stat in STATS:
        score = char.stats.get(stat, 0)
        lines.append(f"  {stat.capitalize():<14} {score:3d}  (x5 {score * 5})")

    lines.append("")
    sanity = f"Sanity: {char.sanity}"
    if char.current_sanity is not None:
        sanity += f" (current {char.current_sanity})"
    lines.append(f"Hit Points: {char.hitpoints}   Willpower: {char.willpower}   {sanity}")
    lines.append(f"Breaking Point: {char.breaking_point}   Damage Bonus: {char.damage_bonus:+d}")
    if char.disorder:
        lines.append(f"Disorder: {char.disorder}")
    if char.adapted_to_violence or char.adapted_to_helplessness:
        lines.append(
            f"Adapted to Violence: {char.adapted_to_violence}   "
            f"Adapted to Helplessness: {char.adapted_to_helplessness}",
        )

    lines.append("")
    lines.append("Skills:")
    for skill in sorted(char.skills):
        lines.append(f"  {skill.title():<20} {char.skills[skill]}%")

    if char.bonds:
        lines.append("")
        lines.append("Bonds:")
        for i, score in char.bonds.items():
            lines.append(f"  Bond {i + 1}: {score}")

    if char.weapons or char.gear_lines:
        lines.append("")
        lines.append("Equipment:")
        for weapon in char.weapons:
            parts = [f"{weapon.name} ({weapon.roll}%)"]
            if weapon.base_range:
                parts.append(f"range {weapon.base_range}")
            if weapon.ap is not None:
                parts.append(f"ap {weapon.ap}")
            if weapon.has_damage and weapon.damage_dice is not None:
                modifier = f"{weapon.damage_modifier:+d}" if weapon.damage_modifier else ""
                parts.append(f"damage {weapon.damage_dice}D{weapon.damage_die_type}{modifier}")
            if weapon.ammo is not None:
                parts.append(f"ammo {weapon.ammo}")
            lines.append(f"  Weapon: {' '.join(parts)}")
        for gear in char.gear_lines:
            # Continuation lines from equipment.py's wrap(..., subsequent_indent="  ") - merge
            # back onto the previous entry instead of prefixing "Gear:" again.
            if gear.startswith("  ") and lines[-1].startswith("  Gear:"):
                lines[-1] += " " + gear.strip()
            else:
                lines.append(f"  Gear: {gear}")

    return "\n".join(lines)
