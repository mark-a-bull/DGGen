"""A character's backstory: who their bonds are, what drives them, and the small details.

Pure state, with no randomness, reportlab or display formatting: `rules/backstory.py` fills it in,
and `summary.py` turns it into the lines the text summary and the PDF's backstory page show. Bond
*scores* stay in `Character.bonds` (that is what the sheet shows); a `BondDetail` only says who the
bond is with.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class BondDetail:
    """One bond: its slot on the sheet (`Character.bonds` key), who it is with, and its score.

    `name` is in the sheet's "SURNAME, Given" order, like `Character.name`.
    """

    slot: int
    relationship: str
    name: str
    score: int


@dataclass(frozen=True)
class Backstory:
    bonds: tuple[BondDetail, ...] = ()
    motivations: tuple[str, ...] = ()
    personal_details: tuple[str, ...] = ()

    def is_empty(self) -> bool:
        return not (self.bonds or self.motivations or self.personal_details)
