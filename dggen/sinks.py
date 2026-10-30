"""Output sinks: where finished characters go.

`generate_roster` yields characters; a sink consumes them. The CLI feeds every character to a
`TextSink` and, with `--pdf`, to a `PdfSink` too. A new format (JSON, markdown, ...) is another
class with these four methods - nothing in generation needs to change.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Protocol

from dggen.pdf import SheetWriter
from dggen.serialize import to_back_fields, to_front_fields
from dggen.summary import format_details

if TYPE_CHECKING:
    from collections.abc import Sequence
    from pathlib import Path

    from dggen.character import Character
    from dggen.models import Profession

logger = logging.getLogger("dggen")


class Sink(Protocol):
    def begin(self, professions: Sequence[Profession]) -> None:
        """Called once, before any character, with the professions about to be generated."""

    def start_profession(self, profession: Profession) -> None:
        """Called before the first character of each profession."""

    def add(self, character: Character) -> None:
        """Called once per finished character."""

    def finish(self) -> None:
        """Called once, after the last character."""


class TextSink:
    """Print each character's readable summary to stdout."""

    def begin(self, professions: Sequence[Profession]) -> None:
        pass

    def start_profession(self, profession: Profession) -> None:
        pass

    def add(self, character: Character) -> None:
        print(format_details(character))
        print()

    def finish(self) -> None:
        pass


class PdfSink:
    """Draw each character onto the sheet and save one PDF at the end."""

    def __init__(
        self,
        output: Path,
        *,
        title: str | None,
        oconus: bool,
        equip: bool,
        count: int | None,
    ) -> None:
        self.output = output
        self.title = title
        self.oconus = oconus
        self.pages_per_sheet = 2 if equip else 1
        self.count = count  # the -c override, so the table of contents can number pages
        self.writer = SheetWriter(output, pages_per_sheet=self.pages_per_sheet)

    def begin(self, professions: Sequence[Profession]) -> None:
        self.writer.add_cover(self.title, self.oconus)
        if len(professions) > 1:
            self.writer.generate_toc(professions, self.pages_per_sheet, self.count)

    def start_profession(self, profession: Profession) -> None:
        self.writer.bookmark(profession.roster_label())

    def add(self, character: Character) -> None:
        self.writer.add_page(to_front_fields(character))
        if self.pages_per_sheet >= 2:
            self.writer.add_page_2(to_back_fields(character))

    def finish(self) -> None:
        self.writer.save_pdf()
        logger.info("Wrote %s", self.output)
