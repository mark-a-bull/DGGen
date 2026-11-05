"""A character's backstory: who their bonds are, what drives them, and the small details.

Pure state and rendering, with no randomness and no reportlab: `rules/backstory.py` fills it in,
`summary.py` prints it and `pdf.py` lays it out on its own page. Bond *scores* stay in
`Character.bonds` (that is what the sheet shows); a `BondDetail` only says who the bond is with.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class BondDetail:
    """One bond: its slot on the sheet (`Character.bonds` key), who it is with, and its score."""

    slot: int
    relationship: str
    name: str
    score: int

    def describe(self) -> str:
        return f"{self.relationship}: {self.name} ({self.score})"


@dataclass(frozen=True)
class Backstory:
    bonds: tuple[BondDetail, ...] = ()
    motivations: tuple[str, ...] = ()
    personal_details: tuple[str, ...] = ()

    def is_empty(self) -> bool:
        return not (self.bonds or self.motivations or self.personal_details)


@dataclass(frozen=True)
class BackstorySection:
    """A heading and its lines, as the text summary and the backstory page both show them."""

    title: str
    lines: tuple[str, ...] = field(default=())


def backstory_sections(backstory: Backstory) -> list[BackstorySection]:
    """The non-empty sections of a backstory, in reading order."""
    sections = []
    if backstory.bonds:
        sections.append(
            BackstorySection("Bonds", tuple(bond.describe() for bond in backstory.bonds))
        )
    if backstory.motivations:
        sections.append(BackstorySection("Motivations", backstory.motivations))
    if backstory.personal_details:
        sections.append(BackstorySection("Personal details", backstory.personal_details))
    return sections
