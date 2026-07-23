"""Equipment: resolving a kit into weapons and gear lines on the character's back page."""

from __future__ import annotations

import logging
from copy import copy
from itertools import chain
from textwrap import shorten, wrap
from typing import TYPE_CHECKING

from dggen.models import KitArmourEntry

if TYPE_CHECKING:
    from collections.abc import Iterable

    from dggen.character import Character
    from dggen.models import Weapon, WeaponRef

logger = logging.getLogger("dggen")

MAX_WEAPONS = 7
MAX_GEAR_LINES = 22


def equip(char: Character, kit_name: str | None = None) -> None:
    weapons = [char.data.weapons["unarmed"]]
    if kit_name:
        kit = char.data.kits[kit_name]
        weapons += build_weapon_list(char, kit.weapons)

        gear = []
        for item in [*kit.armour, *kit.gear]:
            if item.chance < char.rng.randint(1, 100):
                continue
            notes = (
                (" ".join(char.store_footnote(n) for n in item.notes) + " ") if item.notes else ""
            )
            if isinstance(item, KitArmourEntry):
                text = notes + char.data.armour[item.type]
            else:
                text = notes + item.text
            gear.append(text)

        wrapped_gear = list(chain(*[wrap(item, 55, subsequent_indent="  ") for item in gear]))
        if len(wrapped_gear) > MAX_GEAR_LINES:
            logger.warning("Too much gear - truncated.")
        for i, line in enumerate(wrapped_gear):
            char.e[f"gear{i}"] = line

    if len(weapons) > MAX_WEAPONS:
        logger.warning("Too many weapons %s - truncated.", weapons)
    for i, weapon in enumerate(weapons[:MAX_WEAPONS]):
        equip_weapon(char, i, weapon)


def build_weapon_list(char: Character, weapons_to_add: Iterable[WeaponRef]) -> list[Weapon]:
    result = []
    for weapon_to_add in weapons_to_add:
        if weapon_to_add.type is not None:
            weapon = copy(char.data.weapons.get(weapon_to_add.type))
            if weapon:
                if weapon_to_add.notes:
                    weapon.notes = weapon_to_add.notes
                if weapon_to_add.chance >= char.rng.randint(1, 100):
                    result.append(weapon)
            else:
                logger.error("Unknown weapon type %s", weapon_to_add.type)
        elif weapon_to_add.one_of:
            if weapon_to_add.chance >= char.rng.randint(1, 100):
                result += build_weapon_list(char, [char.rng.choice(weapon_to_add.one_of)])
        elif weapon_to_add.both:
            result += build_weapon_list(char, weapon_to_add.both)
        else:
            logger.error("Don't understand weapon %r", weapon_to_add)
    return result


def equip_weapon(char: Character, slot: int, weapon: Weapon) -> None:
    char.e[f"weapon{slot}"] = shorten(weapon.name, 15, placeholder="…")
    roll = int(char.d.get(weapon.skill, 0) + weapon.bonus)
    char.e[f"weapon{slot}_roll"] = f"{roll}%"
    if weapon.base_range is not None:
        char.e[f"weapon{slot}_range"] = weapon.base_range
    if weapon.ap is not None:
        char.e[f"weapon{slot}_ap"] = f"{weapon.ap}"
    if weapon.lethality is not None:
        lethality = weapon.lethality
        lethality_note_indicator = (
            char.store_footnote(lethality.special) if lethality.special else None
        )
        char.e[f"weapon{slot}_lethality"] = (f"{lethality.rating}%" if lethality.rating else "") + (
            f" {lethality_note_indicator}" if lethality_note_indicator else ""
        )

    if weapon.ammo is not None:
        char.e[f"weapon{slot}_ammo"] = f"{weapon.ammo}"
    if weapon.kill_radius is not None:
        char.e[f"weapon{slot}_kill_radius"] = weapon.kill_radius

    if weapon.notes:
        char.e[f"weapon{slot}_note"] = " ".join(char.store_footnote(n) for n in weapon.notes)

    if weapon.damage is not None:
        damage = weapon.damage
        damage_note_indicator = char.store_footnote(damage.special) if damage.special else None

        if damage.dice is not None:
            damage_modifier = damage.modifier + (char.damage_bonus if damage.db_applies else 0)
            damage_roll = f"{damage.dice}D{damage.die_type}" + (
                f"{damage_modifier:+d}" if damage_modifier else ""
            )
        else:
            damage_roll = ""

        char.e[f"weapon{slot}_damage"] = damage_roll + (
            f" {damage_note_indicator}" if damage_note_indicator else ""
        )
