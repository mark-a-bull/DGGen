"""The `Character` aggregate: structured generation state.

`Character` holds typed domain state - stats, skills, bonds, derived attributes, demographics,
psychological state, and equipped weapons/gear. It knows nothing about sheet coordinates or
display formatting. The sheet's field dicts are produced from it by `dggen.serialize`
(`to_front_fields` / `to_back_fields`); the dependency points that way, never from here.

Rule steps live in `dggen.rules.*` as functions that take and mutate a `Character` (via its
`.rng`); this class holds the shared state and the small helpers (`distinguishing`,
`store_footnote`) those steps lean on. `Character.generate(...)` runs them in order.
"""

from __future__ import annotations

import logging
from datetime import date
from textwrap import wrap
from typing import TYPE_CHECKING

from dggen import constants
from dggen.constants import MONTHS
from dggen.options import GenerationOptions
from dggen.rules import equipment
from dggen.rules.pipeline import PIPELINE, enabled_steps
from dggen.text import age_on, format_name

if TYPE_CHECKING:
    from collections.abc import Sequence

    from dggen.equipped import EquippedWeapon
    from dggen.models import Data, Profession
    from dggen.rng import Rng
    from dggen.rules.pipeline import Step

logger = logging.getLogger("dggen")

MAX_NOTE_LINES = 12


class Character:
    def __init__(
        self,
        data: Data,
        rng: Rng,
        sex: str,
        profession: Profession,
        today: date | None = None,
    ) -> None:
        self.data = data
        self.rng = rng
        self.sex = sex
        self.profession = profession
        self.today = today or date.today()  # the date ages are measured against

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
        self.skills: dict[str, int] = {}
        # Sub-skill names ("craft1label" -> "Electrician"), kept apart so `skills` is all numbers.
        self.skill_labels: dict[str, str] = {}
        self.bonds: dict[int, int] = {}
        self.picked_skills: list[str] = []  # the profession's `possible` skills actually chosen
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
        self.footnotes: dict[str, str] = {}  # note text -> marker glyph

    @classmethod
    def generate(
        cls,
        *,
        data: Data,
        rng: Rng,
        sex: str,
        profession: Profession,
        options: GenerationOptions | None = None,
        pipeline: Sequence[Step] = PIPELINE,
    ) -> Character:
        """Run `pipeline` (default: the standard rules, in order) to produce one character."""
        options = options or GenerationOptions()
        char = cls(data, rng, sex, profession, today=options.today)
        for step in enabled_steps(options, pipeline):
            step.run(char, options)
        return char

    def generate_demographics(self, options: GenerationOptions) -> None:
        if options.name_override:
            self.name = format_name(options.name_override)
        elif self.sex == "male":
            self.name = (
                self.data.family_names(self.rng).upper()
                + ", "
                + self.data.male_given_names(self.rng)
            )
        else:
            self.name = (
                self.data.family_names(self.rng).upper()
                + ", "
                + self.data.female_given_names(self.rng)
            )
        self.profession_label = options.label_override or self.profession.label
        self.employer = options.employer_override or ", ".join(
            e for e in [self.profession.employer, self.profession.division] if e
        )
        self.education = options.education_override
        self.town = self.data.towns(self.rng)
        self.nationality = (f"({options.nationality}) " if options.nationality else "") + self.town
        if options.birthdate:
            self.age = age_on(options.birthdate, self.today)
            self.birth_month_abbrev = MONTHS[options.birthdate.month - 1]
            self.birth_day = options.birthdate.day
        elif options.birth_year:
            self.birth_month_abbrev = self.rng.pick(MONTHS)
            self.birth_day = self.rng.roll(1, 28)
            # The age has to agree with the birthday just drawn: whether it has passed this year
            # decides between `this year - birth_year` and one less.
            birthday = date(
                options.birth_year, MONTHS.index(self.birth_month_abbrev) + 1, self.birth_day
            )
            self.age = age_on(birthday, self.today)
        else:
            self.age = self.rng.roll(options.min_age, options.max_age)
            self.birth_month_abbrev = self.rng.pick(MONTHS)
            self.birth_day = self.rng.roll(1, 28)

    def equip(self, kit_name: str | None = None) -> None:
        equipment.equip(self, kit_name)

    def distinguishing(self, field: str, value: int) -> str:
        return self.rng.pick(self.data.distinguishing.get((field, value), [""]))

    def store_footnote(self, note: str) -> str:
        """Register a footnote and return its indicator glyph (the same one for the same note)."""
        if note not in self.footnotes:
            markers = constants.FOOTNOTE_MARKERS
            if len(self.footnotes) < len(markers):
                self.footnotes[note] = markers[len(self.footnotes)]
            else:
                logger.warning("Out of footnote markers; %r shares %r", note, markers[-1])
                self.footnotes[note] = markers[-1]
        return self.footnotes[note]

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

    def __str__(self) -> str:
        return ", ".join(
            str(part)
            for part in (self.name, self.profession_label, self.employer, self.age)
            if part
        )
