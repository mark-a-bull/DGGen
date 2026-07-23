"""Equipment: resolving a kit into structured weapons and gear lines.

Footnote markers are assigned here, in a fixed order (all gear-item notes first, then per weapon:
lethality, then notes, then damage), because that order determines which glyph each note gets.
The presentation layer only formats the already-resolved markers.
"""

from __future__ import annotations

import logging
from copy import copy
from itertools import chain
from textwrap import wrap
from typing import TYPE_CHECKING

from dggen.equipped import EquippedWeapon
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

        char.gear_lines = list(chain(*[wrap(item, 55, subsequent_indent="  ") for item in gear]))
        if len(char.gear_lines) > MAX_GEAR_LINES:
            logger.warning("Too much gear - truncated.")

    if len(weapons) > MAX_WEAPONS:
        logger.warning("Too many weapons %s - truncated.", weapons)
    char.weapons = [build_equipped_weapon(char, weapon) for weapon in weapons[:MAX_WEAPONS]]


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


def build_equipped_weapon(char: Character, weapon: Weapon) -> EquippedWeapon:
    equipped = EquippedWeapon(
        name=weapon.name,
        roll=int(char.skills.get(weapon.skill, 0) + weapon.bonus),
        base_range=weapon.base_range,
        ap=weapon.ap,
        ammo=weapon.ammo,
        kill_radius=weapon.kill_radius,
    )
    if weapon.lethality is not None:
        equipped.has_lethality = True
        equipped.lethality_rating = weapon.lethality.rating
        equipped.lethality_marker = (
            char.store_footnote(weapon.lethality.special) if weapon.lethality.special else None
        )
    if weapon.notes:
        equipped.note_markers = [char.store_footnote(n) for n in weapon.notes]
    if weapon.damage is not None:
        equipped.has_damage = True
        equipped.damage_dice = weapon.damage.dice
        equipped.damage_die_type = weapon.damage.die_type
        equipped.damage_modifier = weapon.damage.modifier + (
            char.damage_bonus if weapon.damage.db_applies else 0
        )
        equipped.damage_marker = (
            char.store_footnote(weapon.damage.special) if weapon.damage.special else None
        )
    return equipped
