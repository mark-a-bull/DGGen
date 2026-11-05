"""Backstory: name each bond, and pick a couple of motivations and personal details.

Runs last in the pipeline, after veterancy and derived attributes, so a bond a damaged veteran lost
is already gone and only the surviving bonds get a person. The value lists are pools under
`dggen/data/pools/backstory/`: add a line to one of those files to widen the choice.

A bond is with family (half the time, and then it shares the character's surname) or with someone
else. Their given name is drawn male or female at random from the same name pools the character's
own name came from, so `--names`/`--male-given-names` etc. apply to them too.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from dggen.backstory import Backstory, BondDetail

if TYPE_CHECKING:
    from dggen.character import Character

FAMILY_POOL = "backstory/bond-family"
OTHER_POOL = "backstory/bond-other"
MOTIVATIONS_POOL = "backstory/motivations"
DETAILS_POOL = "backstory/quirks"

MOTIVATION_COUNT = 2
DETAIL_COUNT = 2

POOL_IDS = (FAMILY_POOL, OTHER_POOL, MOTIVATIONS_POOL, DETAILS_POOL)


def _surname(char: Character) -> str:
    """The character's own family name, as the sheet writes it ("DIGBY" of "DIGBY, Kim")."""
    return char.name.split(",")[0].strip()


def _bond_detail(char: Character, slot: int, score: int) -> BondDetail:
    rng = char.rng
    family = rng.roll(0, 1) == 1
    relationship = char.data.pools.choice(FAMILY_POOL if family else OTHER_POOL, rng)
    given_names = char.data.male_given_names if rng.roll(0, 1) else char.data.female_given_names
    surname = _surname(char) if family else char.data.family_names(rng).upper()
    return BondDetail(slot, relationship, f"{surname}, {given_names(rng)}", score)


def generate_backstory(char: Character) -> None:
    bonds = tuple(_bond_detail(char, slot, score) for slot, score in sorted(char.bonds.items()))
    pools = char.data.pools
    motivations = pools.values(MOTIVATIONS_POOL)
    details = pools.values(DETAILS_POOL)
    char.backstory = Backstory(
        bonds=bonds,
        motivations=tuple(char.rng.sample(motivations, MOTIVATION_COUNT)),
        personal_details=tuple(char.rng.sample(details, DETAIL_COUNT)),
    )
