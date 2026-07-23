"""The `Character` aggregate: structured generation state.

`Character` holds typed domain state - stats, skills, bonds, derived attributes, demographics,
psychological state, and equipped weapons/gear. It knows nothing about sheet coordinates or
display formatting. The `d` (front page) and `e` (back/equipment page) field dicts that the PDF
layer consumes are produced on demand by `dggen.serialize`, exposed here as read-only properties
so the rest of the app (and the tests) can keep using `character.d` / `character.e`.

Rule steps live in `dggen.rules.*` as functions that take and mutate a `Character` (via its
`.rng`); this class holds the shared state and the small helpers (`distinguishing`,
`store_footnote`) those steps lean on. `Character.generate(...)` runs them in order.
"""

from __future__ import annotations

import logging
from collections import defaultdict
from datetime import date, datetime
from textwrap import wrap
from typing import TYPE_CHECKING, Any

from dggen import constants, serialize
from dggen.constants import MONTHS
from dggen.rules import education, employer, equipment, skills, stats, veterancy
from dggen.text import age_on, format_name

if TYPE_CHECKING:
    from dggen.equipped import EquippedWeapon
    from dggen.models import Data, Profession
    from dggen.rng import Rng

logger = logging.getLogger("dggen")

MAX_NOTE_LINES = 12


class Character:
    def __init__(self, data: Data, rng: Rng, sex: str) -> None:
        self.data = data
        self.rng = rng
        self.sex = sex
        self.profession: Profession | None = None

        # Demographics
        self.name = ""
        self.profession_label = ""
        self.employer = ""
        self.education: str | None = None
        self.town = ""
        self.nationality = ""
        self.age = 0
        self.birth_month_abbrev = ""
        self.birth_day = 0

        # Statistics and derived attributes
        self.stats: dict[str, int] = {}
        self.distinguishing_features: dict[str, str] = {}
        self.hitpoints = 0
        self.willpower = 0
        self.sanity = 0
        self.current_sanity: int | None = None
        self.breaking_point = 0
        self.damage_bonus = 0

        # Skills and bonds
        self.skills: dict[str, Any] = {}
        self.bonds: dict[int, int] = {}
        self.bonus_skills: list[str] = []

        # Psychological / veterancy
        self.san_lost = 0
        self.adapted_to_violence = 0
        self.adapted_to_helplessness = 0
        self.disorder: str | None = None
        self.damage_details: list[str] = []

        # Equipment
        self.weapons: list[EquippedWeapon] = []
        self.gear_lines: list[str] = []
        self.note_lines: list[str] = []
        self.footnotes = defaultdict(iter(constants.FOOTNOTE_MARKERS).__next__)

    @classmethod
    def generate(
        cls,
        *,
        data: Data,
        rng: Rng,
        sex: str,
        profession: Profession,
        label_override: str | None = None,
        employer_override: str | None = None,
        name_override: str | None = None,
        education_override: str | None = None,
        min_age: int = 24,
        max_age: int = 55,
        birth_year: int | None = None,
        birthdate: date | None = None,
        nationality: str | None = None,
        veterancy_enabled: bool = False,
        damaged: bool = True,
        auto_education: bool = True,
        auto_employer: bool = True,
    ) -> Character:
        char = cls(data, rng, sex)
        char.profession = profession
        char.generate_demographics(
            label_override,
            employer_override,
            name_override,
            education_override,
            min_age,
            max_age,
            birth_year,
            birthdate,
            nationality,
        )
        if auto_employer:
            employer.generate_employer(char, data.employer)
        stats.generate_stats(char)
        skills.generate_skills(char)
        if auto_education:
            education.generate_education(char, data.education)
        if veterancy_enabled:
            veterancy.apply_veterancy(char, damaged)
        stats.generate_derived_attributes(char)
        return char

    def generate_demographics(
        self,
        label_override: str | None,
        employer_override: str | None,
        name_override: str | None,
        education_override: str | None,
        min_age: int,
        max_age: int,
        birth_year: int | None,
        birthdate: date | None,
        nationality: str | None,
    ) -> None:
        if name_override:
            self.name = format_name(name_override)
        elif self.sex == "male":
            self.name = self.data.family_names().upper() + ", " + self.data.male_given_names()
        else:
            self.name = self.data.family_names().upper() + ", " + self.data.female_given_names()
        self.profession_label = label_override or self.profession.label
        self.employer = employer_override or ", ".join(
            e for e in [self.profession.employer, self.profession.division] if e
        )
        self.education = education_override
        self.town = self.data.towns()
        self.nationality = (f"({nationality}) " if nationality else "") + self.town
        if birthdate:
            self.age = age_on(birthdate, datetime.now().date())
            self.birth_month_abbrev = MONTHS[birthdate.month - 1]
            self.birth_day = birthdate.day
        elif birth_year:
            self.age = datetime.now().year - birth_year
            self.birth_month_abbrev = self.rng.choice(MONTHS)
            self.birth_day = self.rng.randint(1, 28)
        else:
            self.age = self.rng.randint(min_age, max_age)
            self.birth_month_abbrev = self.rng.choice(MONTHS)
            self.birth_day = self.rng.randint(1, 28)

    def equip(self, kit_name: str | None = None) -> None:
        equipment.equip(self, kit_name)

    def distinguishing(self, field: str, value: int) -> str:
        return self.rng.choice(self.data.distinguishing.get((field, value), [""]))

    def store_footnote(self, note: str | None) -> str | None:
        """Register a footnote and return its indicator glyph (or None for a blank note)."""
        return self.footnotes[note] if note else None

    def print_footnotes(self) -> None:
        """Flush registered footnotes into wrapped note lines for the back page."""
        notes = [
            line
            for note, pointer in list(self.footnotes.items())
            for line in wrap(f"{pointer} {note}", 40, subsequent_indent="  ")
        ]
        if len(notes) > MAX_NOTE_LINES:
            logger.warning("Too many footnotes - truncated.")
        self.note_lines = notes[:MAX_NOTE_LINES]

    @property
    def d(self) -> dict[str, Any]:
        """Front-page field dict, produced from structured state on demand."""
        return serialize.to_front_fields(self)

    @property
    def e(self) -> dict[str, Any]:
        """Back / equipment-page field dict, produced from structured state on demand."""
        return serialize.to_back_fields(self)

    def __str__(self) -> str:
        return ", ".join(
            str(part)
            for part in (self.name, self.profession_label, self.employer, self.age)
            if part
        )
