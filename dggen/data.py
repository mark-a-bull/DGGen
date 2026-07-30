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
    from argparse import Namespace

    from dggen.rng import Rng


class ProfessionNotFound(Exception):
    """Raised when a requested profession key/label matches nothing. The CLI turns this into an
    error message and a non-zero exit; library callers can catch it."""

    def __init__(self, requested: str, professions: dict[str, Profession]) -> None:
        valid = ", ".join(f"{key} ({p.label})" for key, p in professions.items())
        super().__init__(f"Unknown profession {requested!r}. Valid options are: {valid}")
        self.requested = requested


def find_profession(professions: dict[str, Profession], type_: str) -> Profession:
    """Resolve a profession by its data key (e.g. 'agent') or display label (e.g. 'Federal Agent'),
    case-insensitively. Raises ProfessionNotFound if nothing matches."""
    if type_ in professions:
        return professions[type_]
    for key, profession in professions.items():
        if key.lower() == type_.lower() or profession.label.lower() == type_.lower():
            return profession
    raise ProfessionNotFound(type_, professions)


def load_data(options: Namespace, rng: Rng) -> Data:
    pools = Pools(config.POOLS_DIR)

    if options.names:
        faker = Faker(options.names)
        if getattr(options, "seed", None) is not None:
            faker.seed_instance(options.seed)
        male_given_names = faker.first_name_male
        female_given_names = faker.first_name_female
        family_names = faker.last_name
    else:
        # Validate eagerly: a bad --male-given-names/etc. should fail at startup, not partway
        # through generating a roster.
        pools.validate(options.male_given_names)
        pools.validate(options.female_given_names)
        pools.validate(options.surnames)

        def male_given_names():
            return pools.choice(options.male_given_names, rng)

        def female_given_names():
            return pools.choice(options.female_given_names, rng)

        def family_names():
            return pools.choice(options.surnames, rng)

    pools.validate(options.towns)

    def towns():
        return pools.choice(options.towns, rng)

    with options.professions.open() as f:
        professions = {k: Profession.from_dict(v) for k, v in json.load(f).items()}
    with options.equipment.open() as f:
        equipment = json.load(f)
        kits = {k: Kit.from_dict(v) for k, v in equipment["kits"].items()}
        weapons = {k: Weapon.from_dict(v) for k, v in equipment["weapons"].items()}
        armour = equipment["armour"]

    distinguishing: dict[tuple[str, int], list[str]] = {}
    with options.distinguishing_features.open() as f:
        for row in csv.DictReader(f):
            for value in range(int(row["from"]), int(row["to"]) + 1):
                distinguishing.setdefault((row["statistic"], value), []).append(
                    row["distinguishing"],
                )

    with options.education_data.open() as f:
        education = EducationData.from_dict(json.load(f))

    with options.employer_data.open() as f:
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
