"""The generation steps, in order, as data.

`Character.generate` used to be a hand-written sequence of calls and `if options.x:` checks, so the
order (which *is* the RNG draw order) and which options switch which step off were implicit.
`PIPELINE` makes both explicit: each `Step` has a name, the function that does it, and an optional
predicate on the options. Adding a rule is adding an entry; reordering shows up as a one-line diff
that the golden snapshot will then hold you to.

Steps take `(char, options)`. They import `Character` only under `TYPE_CHECKING`, like the rule
modules they wrap, to avoid an import cycle.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from dggen.rules import education, employer, skills, stats, veterancy

if TYPE_CHECKING:
    from collections.abc import Callable, Iterable

    from dggen.character import Character
    from dggen.options import GenerationOptions


def _always(_options: GenerationOptions) -> bool:
    return True


@dataclass(frozen=True)
class Step:
    name: str
    run: Callable[[Character, GenerationOptions], None]
    enabled: Callable[[GenerationOptions], bool] = field(default=_always)


def _demographics(char: Character, options: GenerationOptions) -> None:
    char.generate_demographics(options)


def _employer(char: Character, _options: GenerationOptions) -> None:
    employer.generate_employer(char, char.data.employer)


def _stats(char: Character, _options: GenerationOptions) -> None:
    stats.generate_stats(char)


def _skills(char: Character, _options: GenerationOptions) -> None:
    skills.generate_skills(char)


def _education(char: Character, _options: GenerationOptions) -> None:
    education.generate_education(char, char.data.education)


def _veterancy(char: Character, options: GenerationOptions) -> None:
    veterancy.apply_veterancy(char, options.damaged)


def _derived(char: Character, _options: GenerationOptions) -> None:
    stats.generate_derived_attributes(char)


# The order is the RNG draw order. Do not reorder without regenerating (and reviewing) the golden
# snapshot: every seeded character changes.
PIPELINE: tuple[Step, ...] = (
    Step("demographics", _demographics),
    Step("employer", _employer, enabled=lambda options: options.auto_employer),
    Step("stats", _stats),
    Step("skills", _skills),
    Step("education", _education, enabled=lambda options: options.auto_education),
    Step("veterancy", _veterancy, enabled=lambda options: options.veterancy_enabled),
    Step("derived attributes", _derived),
)


def enabled_steps(options: GenerationOptions, steps: Iterable[Step] = PIPELINE) -> list[Step]:
    """The steps that will run for these options, in order."""
    return [step for step in steps if step.enabled(options)]
