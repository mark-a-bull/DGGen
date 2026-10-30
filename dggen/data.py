"""Load the data files into a `Data` object, and look professions up by key or label.

The name/town providers close over the seedable `Rng` so that even name and town selection is
reproducible under a fixed seed.
"""

from __future__ import annotations

import csv
import json
from typing import TYPE_CHECKING

from faker import Faker

from dggen import config
from dggen.models import Data, EducationData, EmployerData, Kit, Profession, Weapon
from dggen.pools import Pools

if TYPE_CHECKING:
    from dggen.options import DataSources
    from dggen.rng import Rng


class ProfessionNotFoundError(Exception):
    """Raised when a requested profession key/label matches nothing. The CLI turns this into an
    error message and a non-zero exit; library callers can catch it."""

    def __init__(self, requested: str, professions: dict[str, Profession]) -> None:
        valid = ", ".join(f"{key} ({p.label})" for key, p in professions.items())
        super().__init__(f"Unknown profession {requested!r}. Valid options are: {valid}")
        self.requested = requested


class InvalidLocaleError(Exception):
    """Raised when `--names` is given a locale Faker doesn't provide."""


def _match_key(professions: dict[str, Profession], type_: str) -> str | None:
    """The profession key `type_` names exactly (ignoring case), if any."""
    if type_ in professions:
        return type_
    return next((key for key in professions if key.lower() == type_.lower()), None)


def ambiguous_keys(professions: dict[str, Profession], type_: str) -> list[str]:
    """Keys of every profession sharing the display label `type_`, if it names more than one.

    Several keys in the variant files share one label ("Federal Agent" is `cid` and `nsb-agent`
    in the FBI set), and a label can't say which was meant. Empty when `type_` is a key (which is
    always exact) or matches at most one label.
    """
    if _match_key(professions, type_) is not None:
        return []
    keys = [key for key, p in professions.items() if p.label.lower() == type_.lower()]
    return keys if len(keys) > 1 else []


def find_profession(professions: dict[str, Profession], type_: str) -> Profession:
    """Resolve a profession by its data key (e.g. 'agent') or display label (e.g. 'Federal Agent'),
    case-insensitively; a key always beats a label. A label shared by several professions
    resolves to the first (see `ambiguous_keys`). Raises ProfessionNotFoundError if nothing
    matches."""
    key = _match_key(professions, type_)
    if key is not None:
        return professions[key]
    for profession in professions.values():
        if profession.label.lower() == type_.lower():
            return profession
    raise ProfessionNotFoundError(type_, professions)


def load_data(sources: DataSources, rng: Rng) -> Data:
    pools = Pools(config.POOLS_DIR)

    if sources.names_locale:
        try:
            faker = Faker(sources.names_locale)
        except AttributeError as exc:  # Faker's way of saying the locale doesn't exist
            raise InvalidLocaleError(
                f"Unknown --names locale {sources.names_locale!r} (e.g. en_US, en_GB)"
            ) from exc
        if sources.seed is not None:
            faker.seed_instance(sources.seed)
        male_given_names = faker.first_name_male
        female_given_names = faker.first_name_female
        family_names = faker.last_name
    else:
        # Validate eagerly: a bad --male-given-names/etc. should fail at startup, not partway
        # through generating a roster.
        pools.validate(sources.male_given_names)
        pools.validate(sources.female_given_names)
        pools.validate(sources.surnames)

        def male_given_names() -> str:
            return pools.choice(sources.male_given_names, rng)

        def female_given_names() -> str:
            return pools.choice(sources.female_given_names, rng)

        def family_names() -> str:
            return pools.choice(sources.surnames, rng)

    pools.validate(sources.towns)

    def towns() -> str:
        return pools.choice(sources.towns, rng)

    with sources.professions.open() as f:
        professions = {k: Profession.from_dict(v) for k, v in json.load(f).items()}
    with sources.equipment.open() as f:
        equipment = json.load(f)
        kits = {k: Kit.from_dict(v) for k, v in equipment["kits"].items()}
        weapons = {k: Weapon.from_dict(v) for k, v in equipment["weapons"].items()}
        armour = equipment["armour"]

    distinguishing: dict[tuple[str, int], list[str]] = {}
    with sources.distinguishing_features.open() as f:
        for row in csv.DictReader(f):
            for value in range(int(row["from"]), int(row["to"]) + 1):
                distinguishing.setdefault((row["statistic"], value), []).append(
                    row["distinguishing"],
                )

    with sources.education_data.open() as f:
        education = EducationData.from_dict(json.load(f))

    with sources.employer_data.open() as f:
        employer = EmployerData.from_dict(json.load(f))

    return Data(
        male_given_names=male_given_names,
        female_given_names=female_given_names,
        family_names=family_names,
        towns=towns,
        professions=professions,
        kits=kits,
        weapons=weapons,
        armour=armour,
        distinguishing=distinguishing,
        education=education,
        employer=employer,
        pools=pools,
    )
