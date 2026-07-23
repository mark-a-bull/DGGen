"""Typed data models loaded from the JSON/CSV data files.

Each dataclass has a `from_dict` classmethod mapping the on-disk (hyphenated) keys onto Python
attributes. `from __future__ import annotations` is required, not cosmetic: several `from_dict`
methods return-annotate with their own class, which would raise NameError at import time under
eager annotation evaluation.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import Callable


@dataclass
class ProfessionSkills:
    fixed: dict[str, int]
    possible: dict[str, int] = field(default_factory=dict)
    possible_count: int = 0
    bonus: list[str] = field(default_factory=list)

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> ProfessionSkills:
        return cls(
            fixed=d["fixed"],
            possible=d.get("possible", {}),
            possible_count=d.get("possible-count", 0),
            bonus=d.get("bonus", []),
        )


@dataclass
class Profession:
    label: str
    number_to_generate: int
    skills: ProfessionSkills
    bonds: int
    equipment_kit: str | None = None
    employer: str = ""
    division: str = ""

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> Profession:
        return cls(
            label=d["label"],
            number_to_generate=d["number_to_generate"],
            skills=ProfessionSkills.from_dict(d["skills"]),
            bonds=d["bonds"],
            equipment_kit=d.get("equipment-kit"),
            employer=d.get("employer", ""),
            division=d.get("division", ""),
        )


@dataclass
class Damage:
    dice: int | None = None
    die_type: int | None = None
    modifier: int = 0
    db_applies: bool = False
    special: str | None = None

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> Damage:
        return cls(
            dice=d.get("dice"),
            die_type=d.get("die-type"),
            modifier=d.get("modifier", 0),
            db_applies=d.get("db-applies", False),
            special=d.get("special"),
        )


@dataclass
class Lethality:
    rating: int
    special: str | None = None

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> Lethality:
        return cls(rating=d["rating"], special=d.get("special"))


@dataclass
class Weapon:
    name: str
    skill: str
    base_range: str | None = None
    damage: Damage | None = None
    bonus: int = 0
    lethality: Lethality | None = None
    kill_radius: str | None = None
    ammo: int | None = None
    ap: int | None = None
    notes: list[str] = field(default_factory=list)

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> Weapon:
        return cls(
            name=d["name"],
            skill=d["skill"],
            base_range=d.get("base-range"),
            damage=Damage.from_dict(d["damage"]) if "damage" in d else None,
            bonus=d.get("bonus", 0),
            lethality=Lethality.from_dict(d["lethality"]) if "lethality" in d else None,
            kill_radius=d.get("kill-radius"),
            ammo=d.get("ammo"),
            ap=d.get("ap"),
        )


@dataclass
class WeaponRef:
    type: str | None = None
    one_of: list[WeaponRef] = field(default_factory=list)
    both: list[WeaponRef] = field(default_factory=list)
    chance: int = 100
    notes: list[str] = field(default_factory=list)

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> WeaponRef:
        return cls(
            type=d.get("type"),
            one_of=[WeaponRef.from_dict(w) for w in d.get("one-of", [])],
            both=[WeaponRef.from_dict(w) for w in d.get("both", [])],
            chance=d.get("chance", 100),
            notes=d.get("notes", []),
        )


@dataclass
class KitArmourEntry:
    type: str
    chance: int = 100
    notes: list[str] = field(default_factory=list)

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> KitArmourEntry:
        return cls(type=d["type"], chance=d.get("chance", 100), notes=d.get("notes", []))


@dataclass
class KitGearEntry:
    text: str
    chance: int = 100
    notes: list[str] = field(default_factory=list)

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> KitGearEntry:
        return cls(text=d["text"], chance=d.get("chance", 100), notes=d.get("notes", []))


@dataclass
class Kit:
    weapons: list[WeaponRef]
    armour: list[KitArmourEntry]
    gear: list[KitGearEntry]

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> Kit:
        return cls(
            weapons=[WeaponRef.from_dict(w) for w in d["weapons"]],
            armour=[KitArmourEntry.from_dict(a) for a in d["armour"]],
            gear=[KitGearEntry.from_dict(g) for g in d.get("gear", [])],
        )


@dataclass
class Data:
    """Everything loaded from disk, ready for generation. Name/town providers are callables."""

    male_given_names: Callable[[], str]
    female_given_names: Callable[[], str]
    family_names: Callable[[], str]
    towns: Callable[[], str]
    professions: dict[str, Profession]
    kits: dict[str, Kit]
    weapons: dict[str, Weapon]
    armour: dict[str, str]
    distinguishing: dict[tuple[str, int], list[str]]
