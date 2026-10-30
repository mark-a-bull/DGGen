"""The generation pipeline as a library call: professions in, finished characters out.

`generate_roster` is what the CLI does between parsing options and writing output, with no
argparse, printing or PDF in it, so other front ends (a script, a notebook, a web handler) can
reuse it and a new output format is just another consumer of the characters it yields.
"""

from __future__ import annotations

from itertools import cycle, islice
from typing import TYPE_CHECKING

from dggen.character import Character

if TYPE_CHECKING:
    from collections.abc import Iterable, Iterator

    from dggen.models import Data, Profession
    from dggen.options import GenerationOptions
    from dggen.rng import Rng


def generate_character(
    data: Data,
    rng: Rng,
    sex: str,
    profession: Profession,
    options: GenerationOptions,
    *,
    equip: bool = True,
) -> Character:
    """One finished character: generated, equipped from the profession's kit, footnotes flushed.

    The order matters (footnote markers are assigned while equipping, and the note lines can only
    be flushed after that), which is why callers should use this rather than repeating the steps.
    """
    character = Character.generate(
        data=data, rng=rng, sex=sex, profession=profession, options=options
    )
    if equip:
        character.equip(profession.equipment_kit)
    character.print_footnotes()
    return character


def generate_roster(
    data: Data,
    rng: Rng,
    professions: Iterable[Profession],
    options: GenerationOptions,
    *,
    count: int | None = None,
    sex: str | None = None,
    equip: bool = True,
) -> Iterator[tuple[Profession, Character]]:
    """Yield `(profession, character)` for each character, lazily and in order.

    `count` characters are made per profession (default: the profession's own
    `number_to_generate`). Sexes alternate female, male, ... within each profession unless `sex`
    fixes one. Everything draws from `rng`, so a seeded `Rng` reproduces the whole roster.
    """
    for profession in professions:
        sexes = cycle([sex] if sex else ["female", "male"])
        for current_sex in islice(sexes, count or profession.number_to_generate):
            yield (
                profession,
                generate_character(data, rng, current_sex, profession, options, equip=equip),
            )
