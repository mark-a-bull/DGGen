"""Serialize a `Character`'s structured state into the `d` / `e` sheet-field dicts.

This is the one place that knows about sheet field names and display formatting (checkbox marks,
x5 multiples, the "DB=%d" string, weapon roll/damage strings, ...). The domain layer produces
values; this turns them into what the PDF layer draws. Kept reportlab-free.
"""

from __future__ import annotations

from textwrap import shorten
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from dggen.character import Character
    from dggen.equipped import EquippedWeapon


def to_front_fields(char: Character) -> dict[str, Any]:
    d: dict[str, Any] = {}

    d["male" if char.sex == "male" else "female"] = "X"
    d["name"] = char.name
    d["profession"] = char.profession_label
    d["employer"] = char.employer
    if char.education:
        d["education"] = char.education
    d["nationality"] = char.nationality
    d["age"] = "%d    (%s %d)" % (char.age, char.birth_month_abbrev, char.birth_day)

    for stat, score in char.stats.items():
        d[stat] = score
        d[f"{stat}_x5"] = score * 5
        d[f"{stat}_distinguishing"] = char.distinguishing_features.get(stat, "")

    d["hitpoints"] = char.hitpoints
    d["willpower"] = char.willpower
    d["sanity"] = char.sanity
    if char.current_sanity is not None:
        d["current_sanity"] = char.current_sanity
    d["breaking point"] = char.breaking_point
    d["damage bonus"] = "DB=%d" % char.damage_bonus

    d.update(char.skills)
    for i, value in char.bonds.items():
        d[f"bond{i}"] = value

    if char.disorder:
        d["disorder0"] = "Disorder: " + char.disorder
    d["violence"] = "  ".join("X" for _ in range(char.adapted_to_violence))
    d["helplessness"] = "  ".join("X" for _ in range(char.adapted_to_helplessness))

    return d


def _weapon_fields(slot: int, w: EquippedWeapon) -> dict[str, Any]:
    fields: dict[str, Any] = {
        f"weapon{slot}": shorten(w.name, 15, placeholder="…"),
        f"weapon{slot}_roll": f"{w.roll}%",
    }
    if w.base_range is not None:
        fields[f"weapon{slot}_range"] = w.base_range
    if w.ap is not None:
        fields[f"weapon{slot}_ap"] = f"{w.ap}"
    if w.has_lethality:
        fields[f"weapon{slot}_lethality"] = (
            f"{w.lethality_rating}%" if w.lethality_rating else ""
        ) + (f" {w.lethality_marker}" if w.lethality_marker else "")
    if w.ammo is not None:
        fields[f"weapon{slot}_ammo"] = f"{w.ammo}"
    if w.kill_radius is not None:
        fields[f"weapon{slot}_kill_radius"] = w.kill_radius
    if w.note_markers:
        fields[f"weapon{slot}_note"] = " ".join(w.note_markers)
    if w.has_damage:
        if w.damage_dice is not None:
            damage_roll = f"{w.damage_dice}D{w.damage_die_type}" + (
                f"{w.damage_modifier:+d}" if w.damage_modifier else ""
            )
        else:
            damage_roll = ""
        fields[f"weapon{slot}_damage"] = damage_roll + (
            f" {w.damage_marker}" if w.damage_marker else ""
        )
    return fields


def to_back_fields(char: Character) -> dict[str, Any]:
    e: dict[str, Any] = {}
    for slot, weapon in enumerate(char.weapons):
        e.update(_weapon_fields(slot, weapon))
    for i, line in enumerate(char.gear_lines):
        e[f"gear{i}"] = line
    for i, line in enumerate(char.note_lines):
        e[f"note{i}"] = line
    for i, detail in enumerate(char.damage_details):
        e[f"detail{i}"] = detail
    return e
