"""Plain, typed option bundles for the library API.

The CLI parses argv into an `argparse.Namespace`; everything below that layer takes these
dataclasses instead, so `load_data` and `Character.generate` can be used (and tested) without
going through argparse, and adding an option means adding a field here rather than threading one
more positional argument through several call sites.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from pathlib import Path

from dggen import config


@dataclass(frozen=True)
class DataSources:
    """Where `load_data` reads its data from.

    The structured-config fields are file paths. The four pool fields are a pool id (see
    `dggen/data/pools/README.md`) or a path to your own file. `names_locale` switches name
    generation to Faker for that locale (e.g. "en_GB"); `seed` seeds that Faker instance.
    """

    professions: Path = config.DEFAULT_PROFESSIONS
    equipment: Path = config.DEFAULT_EQUIPMENT
    distinguishing_features: Path = config.DEFAULT_DISTINGUISHING
    education_data: Path = config.DEFAULT_EDUCATION_DATA
    employer_data: Path = config.DEFAULT_EMPLOYER_DATA
    male_given_names: str = config.DEFAULT_MALE_NAMES
    female_given_names: str = config.DEFAULT_FEMALE_NAMES
    surnames: str = config.DEFAULT_SURNAMES
    towns: str = config.DEFAULT_TOWNS
    names_locale: str | None = None
    seed: int | None = None


@dataclass(frozen=True)
class GenerationOptions:
    """Everything that shapes one character beyond its sex and profession."""

    label_override: str | None = None
    employer_override: str | None = None
    name_override: str | None = None
    education_override: str | None = None
    min_age: int = 24
    max_age: int = 55
    birth_year: int | None = None
    birthdate: date | None = None
    nationality: str | None = None
    veterancy_enabled: bool = False
    damaged: bool = True
    auto_education: bool = True
    auto_employer: bool = True
