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

    from dggen.pools import Pools


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
class EducationTier:
    """A level of schooling (e.g. 'bachelors'): the age it's typically completed at, which
    institution list it draws from by default, and its sheet template(s).

    `templates` maps a variant name to a template string. Tiers with only one phrasing use the
    key "default"; tiers whose phrasing depends on the field (bachelors/masters: "B.S." vs
    "B.A.") use "science"/"arts", picked deterministically by field rather than at random - see
    EducationData.science_fields.
    """

    grad_age: int
    templates: dict[str, str]
    institution_pool: str

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> EducationTier:
        return cls(
            grad_age=d["grad_age"],
            templates=d["templates"],
            institution_pool=d["institution_pool"],
        )


@dataclass
class EducationProfession:
    """Which tiers a profession can roll (weighted), what {field} values to fill templates with,
    and any per-tier institution pool override (e.g. a firefighter's 'academy' tier should draw
    from fire academies, not the generic military-basic-training pool)."""

    tiers: dict[str, int]
    fields: list[str] = field(default_factory=list)
    institution_pool_overrides: dict[str, str] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> EducationProfession:
        return cls(
            tiers=d["tiers"],
            fields=d.get("fields", []),
            institution_pool_overrides=d.get("institution_pool_overrides", {}),
        )


@dataclass
class EducationData:
    tier_defaults: dict[str, EducationTier]
    professions: dict[str, EducationProfession]
    # Id of the pool (in data/pools/) listing field names that take a "B.S./M.S." (rather than
    # "B.A./M.A.") degree, e.g. "Computer Science". Anything not in that pool defaults to
    # "B.A./M.A.". Institution and field-name value lists themselves live in data/pools/, not
    # here - this dataclass only holds pool *ids* (resolved against Data.pools at generation
    # time), not the values.
    science_fields_pool: str = "fields/science"

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> EducationData:
        return cls(
            tier_defaults={k: EducationTier.from_dict(v) for k, v in d["tier_defaults"].items()},
            professions={k: EducationProfession.from_dict(v) for k, v in d["professions"].items()},
            science_fields_pool=d.get("science_fields_pool", "fields/science"),
        )


@dataclass
class EmployerOption:
    """One weighted way to fill in a profession's employer: a name drawn from a shared `pool`
    (an id resolved against `Data.pools`, e.g. "employers/federal-law"), a `{city}` `template`
    resolved against the character's hometown, or a fixed `literal`. Exactly one of the three
    should be set; an option with none of them resolves to a blank employer."""

    weight: int = 1
    pool: str | None = None
    template: str | None = None
    literal: str | None = None

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> EmployerOption:
        return cls(
            weight=d.get("weight", 1),
            pool=d.get("pool"),
            template=d.get("template"),
            literal=d.get("literal"),
        )


@dataclass
class EmployerProfession:
    options: list[EmployerOption]

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> EmployerProfession:
        return cls(options=[EmployerOption.from_dict(o) for o in d["options"]])


@dataclass
class EmployerData:
    professions: dict[str, EmployerProfession]

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> EmployerData:
        return cls(
            professions={k: EmployerProfession.from_dict(v) for k, v in d["professions"].items()},
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
    education: EducationData
    employer: EmployerData
    pools: Pools
