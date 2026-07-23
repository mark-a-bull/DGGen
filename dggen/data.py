"""Load the data files into a `Data` object, and look professions up by key or label.

The name/town providers close over the seedable `Rng` so that even name and town selection is
reproducible under a fixed seed.
"""

from __future__ import annotations

import csv
import itertools
import json
from typing import TYPE_CHECKING

from faker import Faker

from dggen.models import Data, Kit, Profession, Weapon

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
    if options.names:
        faker = Faker(options.names)
        if getattr(options, "seed", None) is not None:
            faker.seed_instance(options.seed)
        male_given_names = faker.first_name_male
        female_given_names = faker.first_name_female
        family_names = faker.last_name
    else:
        with options.male_given_names.open() as f:
            _male = f.read().splitlines()
        with options.female_given_names.open() as f:
            _female = f.read().splitlines()
        with options.surnames.open() as f:
            _surnames = f.read().splitlines()

        def male_given_names():
            return rng.choice(_male)

        def female_given_names():
            return rng.choice(_female)

        def family_names():
            return rng.choice(_surnames)

    with options.towns.open() as f:
        if options.towns.suffix == ".csv":
            rows = list(csv.DictReader(f))
            _towns = [r["town"] for r in rows]
            _pops = list(itertools.accumulate(int(r["pop"]) for r in rows))
        else:
            _towns, _pops = f.read().splitlines(), None

    def towns():
        return rng.choices(_towns, cum_weights=_pops, k=1)[0]

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
    )
