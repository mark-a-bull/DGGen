"""The `Character` aggregate: mutable generation state plus the orchestration entry point.

A `Character` accumulates its sheet values into two plain dicts, `d` (front page) and `e` (back /
equipment page), keyed by field name. Those dicts are the *only* contract with the PDF layer, so
the domain never imports anything about coordinates or reportlab.

Rule steps live in `dggen.rules.*` as functions that take and mutate a `Character`; this class
holds the shared state and the small helpers (`distinguishing`, `store_footnote`, ...) those
steps lean on. `Character.generate(...)` runs them in order.
"""

from __future__ import annotations

import logging
from collections import defaultdict
from datetime import date, datetime
from textwrap import wrap
from typing import TYPE_CHECKING, Any

from dggen import constants
from dggen.constants import MONTHS
from dggen.rules import equipment, skills, stats, veterancy
from dggen.text import age_on, format_name

if TYPE_CHECKING:
    from dggen.models import Data, Profession
    from dggen.rng import Rng

logger = logging.getLogger("dggen")


class Character:
    def __init__(self, data: Data, rng: Rng, sex: str) -> None:
        self.data = data
        self.rng = rng
        self.sex = sex
        self.profession: Profession | None = None

        self.san_lost = 0
        self.adapted_to_violence = 0
        self.adapted_to_helplessness = 0
        self.age = 0
        self.damage_bonus = 0
        self.bonus_skills: list[str] = []

        # Sheet field dicts: d = front page, e = back / equipment page.
        self.d: dict[str, Any] = {}
        self.e: dict[str, Any] = {}

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
        stats.generate_stats(char)
        skills.generate_skills(char)
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
        if self.sex == "male":
            self.d["male"] = "X"
            self.d["name"] = self.data.family_names().upper() + ", " + self.data.male_given_names()
        else:
            self.d["female"] = "X"
            self.d["name"] = (
                self.data.family_names().upper() + ", " + self.data.female_given_names()
            )
        if name_override:
            self.d["name"] = format_name(name_override)
        self.d["profession"] = label_override or self.profession.label
        self.d["employer"] = employer_override or ", ".join(
            e for e in [self.profession.employer, self.profession.division] if e
        )
        if education_override:
            self.d["education"] = education_override
        self.d["nationality"] = (f"({nationality}) " if nationality else "") + self.data.towns()
        if birthdate:
            self.age = age_on(birthdate, datetime.now().date())
            self.d["age"] = "%d    (%s %d)" % (self.age, MONTHS[birthdate.month - 1], birthdate.day)
        elif birth_year:
            self.age = datetime.now().year - birth_year
            self.d["age"] = "%d    (%s %d)" % (self.age, self.rng.choice(MONTHS), self.rng.randint(1, 28))
        else:
            self.age = self.rng.randint(min_age, max_age)
            self.d["age"] = "%d    (%s %d)" % (self.age, self.rng.choice(MONTHS), self.rng.randint(1, 28))

    def equip(self, kit_name: str | None = None) -> None:
        equipment.equip(self, kit_name)

    def distinguishing(self, field: str, value: int) -> str:
        return self.rng.choice(self.data.distinguishing.get((field, value), [""]))

    def store_footnote(self, note: str | None) -> str | None:
        """Register a footnote and return its indicator glyph (or None for a blank note)."""
        return self.footnotes[note] if note else None

    def print_footnotes(self) -> None:
        notes = [
            line
            for note, pointer in list(self.footnotes.items())
            for line in wrap(f"{pointer} {note}", 40, subsequent_indent="  ")
        ]
        if len(notes) > 12:
            logger.warning("Too many footnotes - truncated.")
        for i, note in enumerate(notes[:12]):
            self.e[f"note{i}"] = note

    def __str__(self) -> str:
        return ", ".join(
            self.d.get(i)
            for i in ("name", "profession", "employer", "department", "age")
            if self.d.get(i)
        )
