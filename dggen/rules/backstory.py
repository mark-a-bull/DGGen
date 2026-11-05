"""Backstory: name each bond, and pick a couple of motivations and personal details.

Drawn by `roster.generate_character` once everything else (veterancy and equipment included) is
final, so a bond a damaged veteran lost is already gone and only the surviving bonds get a person.
Every draw here comes from `char.rng.fork()`, a generator derived from the main stream's state
without advancing it. That is what keeps a seeded roster exactly as it was before the backstory
existed: the main stream, which the next character's name, stats and gear come from, never sees it.

The value lists are pools under `dggen/data/pools/backstory/`: add a line to one of those files to
widen the choice.

A bond is with family (half the time, and then it shares the character's surname) or with someone
else. A relationship line may end `|male` or `|female` ("father|male"), and then the person's given
name comes from that name pool; an untagged one ("cousin") is either, at random. The names come
from the same pools as the character's own, so `--names`/`--male-given-names` etc. apply to them.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from dggen.backstory import Backstory, BondDetail

if TYPE_CHECKING:
    from collections.abc import Sequence

    from dggen.character import Character
    from dggen.rng import Rng

FAMILY_POOL = "backstory/bond-family"
OTHER_POOL = "backstory/bond-other"
MOTIVATIONS_POOL = "backstory/motivations"
DETAILS_POOL = "backstory/quirks"

MOTIVATION_COUNT = 2
DETAIL_COUNT = 2

POOL_IDS = (FAMILY_POOL, OTHER_POOL, MOTIVATIONS_POOL, DETAILS_POOL)

MALE = "male"
FEMALE = "female"
SEX_TAGS = (MALE, FEMALE)


def split_tag(entry: str) -> tuple[str, str | None]:
    """("father", "male") from "father|male"; ("cousin", None) from an untagged "cousin".

    An unrecognised tag stays part of the text, so a typo is visible in the output and
    `validate.validate_backstory` reports it at startup.
    """
    text, bar, tag = entry.rpartition("|")
    tag = tag.strip()
    if bar and tag in SEX_TAGS:
        return text.strip(), tag
    return entry, None


def distinct(values: Sequence[str]) -> list[str]:
    """`values` without repeats, in order: `Rng.sample` picks positions, so a line repeated in a
    pool could otherwise be drawn twice."""
    return list(dict.fromkeys(values))


def _surname(char: Character) -> str | None:
    """The character's own family name, as the sheet writes it ("DIGBY" of "DIGBY, Kim").

    A name with no comma (`--name "Smith Jr."` gives "SMITH Jr.") has only a surname and maybe a
    suffix, so take its first word. None when there is nothing to take (`--name ", Kim"`).
    """
    head, comma, _ = char.name.partition(",")
    words = head.split()
    if not words:
        return None
    return head.strip() if comma else words[0]


def _coin(rng: Rng) -> bool:
    return rng.roll(0, 1) == 1


def _bond_detail(char: Character, rng: Rng, slot: int, score: int) -> BondDetail:
    family = _coin(rng)
    relationship, sex = split_tag(
        char.data.pools.choice(FAMILY_POOL if family else OTHER_POOL, rng)
    )
    if sex is None:
        sex = MALE if _coin(rng) else FEMALE
    given_names = char.data.male_given_names if sex == MALE else char.data.female_given_names
    # Family shares the character's surname; anyone else, or a family bond when the character
    # has no usable surname, gets one of their own.
    surname = (_surname(char) if family else None) or char.data.family_names(rng).upper()
    return BondDetail(slot, relationship, f"{surname}, {given_names(rng)}", score)


def generate_backstory(char: Character) -> None:
    rng = char.rng.fork()  # never draw from char.rng itself: see the module docstring
    bonds = tuple(
        _bond_detail(char, rng, slot, score) for slot, score in sorted(char.bonds.items())
    )
    pools = char.data.pools
    motivations = distinct(pools.values(MOTIVATIONS_POOL))
    details = distinct(pools.values(DETAILS_POOL))
    char.backstory = Backstory(
        bonds=bonds,
        motivations=tuple(rng.sample(motivations, MOTIVATION_COUNT)),
        personal_details=tuple(rng.sample(details, DETAIL_COUNT)),
    )
