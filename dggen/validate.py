"""Check that everything the data files point at actually exists, when the data loads.

The JSON files reference each other and the value pools by plain strings (a kit name, a weapon
type, a pool id, a tier name). A typo in one used to surface only when generation first reached
it - often partway through a roster, as a bare KeyError. `validate_data` checks every such
reference up front and reports all the problems at once.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from dggen.errors import DataError
from dggen.layout import load_layout
from dggen.pools import PoolError
from dggen.rules import backstory

if TYPE_CHECKING:
    from collections.abc import Callable

    from dggen.layout import SheetLayout
    from dggen.models import Data, WeaponRef


def validate_data(data: Data, layout: SheetLayout | None = None) -> None:
    """Raise `DataError` listing every dangling reference in `data`; return quietly if none.

    `layout` is the sheet layout skills are checked against (default: the bundled one).
    """
    problems: list[str] = []

    def check_pool(where: str, ref: str) -> None:
        try:
            data.pools.validate(ref)
        except PoolError:
            problems.append(f"{where}: no pool or file {ref!r}")

    _education(data, problems, check_pool)
    _employer(data, problems, check_pool)
    _equipment(data, problems)
    _skills(data, problems, layout or load_layout())

    _raise_if_any(problems)


def validate_backstory(data: Data) -> None:
    """Raise `DataError` if the backstory pools are missing or too short to draw from.

    Separate from `validate_data` because the backstory is optional (`--no-backstory`): data
    without these pools is still valid for a run that does not ask for one. The CLI calls this
    when it does, so a bad pool exits 2 at startup instead of failing partway through a roster.
    """
    problems: list[str] = []
    needed = {
        backstory.FAMILY_POOL: 1,
        backstory.OTHER_POOL: 1,
        backstory.MOTIVATIONS_POOL: backstory.MOTIVATION_COUNT,
        backstory.DETAILS_POOL: backstory.DETAIL_COUNT,
    }
    for ref, minimum in needed.items():
        try:
            values = data.pools.values(ref)
        except PoolError as exc:
            problems.append(f"backstory pool {ref!r}: {exc}")
            continue
        if len(backstory.distinct(values)) < minimum:
            problems.append(f"backstory pool {ref!r}: needs at least {minimum} different values")
    for ref in (backstory.FAMILY_POOL, backstory.OTHER_POOL):
        try:
            values = data.pools.values(ref)
        except PoolError:
            continue  # reported above
        for value in values:
            text, tag = backstory.split_tag(value)
            if not text or (tag is None and "|" in value):
                problems.append(
                    f"backstory pool {ref!r}: {value!r} should be 'relationship' or "
                    "'relationship|male' or 'relationship|female'"
                )
    _raise_if_any(problems)


def _raise_if_any(problems: list[str]) -> None:
    if problems:
        count = len(problems)
        plural = "problem" if count == 1 else "problems"
        raise DataError(f"Invalid data ({count} {plural}):\n  - " + "\n  - ".join(problems))


def _education(data: Data, problems: list[str], check_pool: Callable[[str, str], None]) -> None:
    education = data.education
    check_pool("education science_fields_pool", education.science_fields_pool)
    for tier_name, tier in education.tier_defaults.items():
        check_pool(f"education tier {tier_name!r} institution_pool", tier.institution_pool)
    if "_default" not in education.professions:
        problems.append("education professions: no '_default' entry to fall back to")
    for label, profession in education.professions.items():
        problems.extend(
            f"education profession {label!r}: unknown tier {tier_name!r}"
            for tier_name in profession.tiers
            if tier_name not in education.tier_defaults
        )
        for tier_name, pool in profession.institution_pool_overrides.items():
            if tier_name not in education.tier_defaults:
                problems.append(
                    f"education profession {label!r}: override for unknown tier {tier_name!r}"
                )
            check_pool(f"education profession {label!r} override for {tier_name!r}", pool)


def _employer(data: Data, problems: list[str], check_pool: Callable[[str, str], None]) -> None:
    if "_default" not in data.employer.professions:
        problems.append("employer professions: no '_default' entry to fall back to")
    for label, profession in data.employer.professions.items():
        for option in profession.options:
            if option.pool is not None:
                check_pool(f"employer profession {label!r}", option.pool)


def _equipment(data: Data, problems: list[str]) -> None:
    if "unarmed" not in data.weapons:
        problems.append("equipment: no 'unarmed' weapon (every character carries one)")

    def check_weapons(kit: str, refs: list[WeaponRef]) -> None:
        for ref in refs:
            if ref.type is not None and ref.type not in data.weapons:
                problems.append(f"equipment kit {kit!r}: unknown weapon {ref.type!r}")
            check_weapons(kit, ref.one_of)
            check_weapons(kit, ref.both)

    for kit_name, kit in data.kits.items():
        check_weapons(kit_name, kit.weapons)
        problems.extend(
            f"equipment kit {kit_name!r}: unknown armour {armour.type!r}"
            for armour in kit.armour
            if armour.type not in data.armour
        )
    problems.extend(
        f"profession {key!r}: unknown equipment kit {profession.equipment_kit!r}"
        for key, profession in data.professions.items()
        if profession.equipment_kit and profession.equipment_kit not in data.kits
    )


def _skills(data: Data, problems: list[str], layout: SheetLayout) -> None:
    """Every skill a profession names needs a place on the sheet, or it silently never prints."""
    for key, profession in data.professions.items():
        skills = profession.skills
        names = [*skills.fixed, *skills.possible, *skills.bonus]
        problems.extend(
            f"profession {key!r}: skill {name!r} has no field on the sheet layout"
            for name in dict.fromkeys(names)
            if name not in layout.fields
        )
