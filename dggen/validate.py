"""Check that everything the data files point at actually exists, when the data loads.

The JSON files reference each other and the value pools by plain strings (a kit name, a weapon
type, a pool id, a tier name). A typo in one used to surface only when generation first reached
it - often partway through a roster, as a bare KeyError. `validate_data` checks every such
reference up front and reports all the problems at once.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from dggen.pools import PoolError

if TYPE_CHECKING:
    from collections.abc import Callable

    from dggen.models import Data, WeaponRef


class DataError(Exception):
    """The data files are inconsistent: a reference points at something that doesn't exist."""


def validate_data(data: Data) -> None:
    """Raise `DataError` listing every dangling reference in `data`; return quietly if none."""
    problems: list[str] = []

    def check_pool(where: str, ref: str) -> None:
        try:
            data.pools.validate(ref)
        except PoolError:
            problems.append(f"{where}: no pool or file {ref!r}")

    _education(data, problems, check_pool)
    _employer(data, problems, check_pool)
    _equipment(data, problems)

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
