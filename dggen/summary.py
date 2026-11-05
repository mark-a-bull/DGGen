"""A readable plain-text summary of a generated character (what the CLI prints without --pdf).

Reads `Character`'s own fields directly rather than the sheet-keyed `d`/`e` dicts from
`dggen.serialize`: those are formatted for the PDF layer (checkbox marks, `_x5` suffixes, "DB=%d"
strings), not for reading as text.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from dggen.constants import STATS

if TYPE_CHECKING:
    from dggen.backstory import Backstory, BondDetail
    from dggen.character import Character
    from dggen.equipped import EquippedWeapon


@dataclass(frozen=True)
class BackstorySection:
    """A heading and its lines, as the text summary and the PDF's backstory page both show them."""

    title: str
    lines: tuple[str, ...] = ()


def describe_bond(bond: BondDetail) -> str:
    """ "mentor: Sam ROE (9)": the relationship, the person in reading order, and the score.

    The sheet writes names "SURNAME, Given"; that order reads badly inside a sentence-like line.
    """
    surname, _, given = bond.name.partition(", ")
    person = f"{given} {surname}" if given else surname
    return f"{bond.relationship}: {person} ({bond.score})"


def backstory_sections(backstory: Backstory) -> list[BackstorySection]:
    """The non-empty sections of a backstory, in reading order."""
    sections = []
    if backstory.bonds:
        sections.append(
            BackstorySection("Bonds", tuple(describe_bond(bond) for bond in backstory.bonds))
        )
    if backstory.motivations:
        sections.append(BackstorySection("Motivations", backstory.motivations))
    if backstory.personal_details:
        sections.append(BackstorySection("Personal details", backstory.personal_details))
    return sections


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
    if char.backstory and not char.backstory.is_empty():
        # Named bonds replace the bare scores; motivations and details follow.
        sections.extend(
            [f"{section.title}:", *(f"  {line}" for line in section.lines)]
            for section in backstory_sections(char.backstory)
        )
    elif char.bonds:
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
