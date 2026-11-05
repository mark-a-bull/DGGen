"""Presentation layer: draw the field dicts onto the Delta Green character sheet PDF.

The sheet layout (`dggen/data/sheet-layout.json`, loaded by `dggen.layout`) is the single source of
truth mapping a field name to its `(x, y, font_size)` on the background image. The domain layer
produces dicts keyed by these names; `SheetWriter` looks each key up and draws it. Unknown keys
are logged and skipped, never raised.
"""

from __future__ import annotations

import logging
from datetime import datetime
from textwrap import shorten
from typing import TYPE_CHECKING, Any

from reportlab.lib.utils import simpleSplit
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas

from dggen import appearance
from dggen.layout import load_layout
from dggen.text import shrink_to_fit

if TYPE_CHECKING:
    from collections.abc import Iterable
    from pathlib import Path

    from dggen.backstory import BackstorySection
    from dggen.layout import SheetLayout
    from dggen.models import Profession
    from dggen.serialize import FieldValue

logger = logging.getLogger("dggen")


class SheetWriter:
    def __init__(
        self,
        filename: Path,
        pages_per_sheet: int = 1,
        layout: SheetLayout | None = None,
    ) -> None:
        self.layout = layout or load_layout()
        self.filename = filename
        self.pages_per_sheet = pages_per_sheet
        self.c = canvas.Canvas(str(self.filename))
        self.c.setPageSize(appearance.PAGE_SIZE)
        self.c.setAuthor("https://github.com/jimstorch/DGGen")
        self.c.setTitle("Delta Green Agent Roster")
        self.c.setSubject("Pre-generated characters for the Delta Green RPG")
        pdfmetrics.registerFont(TTFont(appearance.DEFAULT_FONT, str(appearance.DEFAULT_FONT_FILE)))
        pdfmetrics.registerFont(TTFont(appearance.OCR_FONT, str(appearance.OCR_FONT_FILE)))

    def _measure(self, text: str, size: int) -> float:
        return pdfmetrics.stringWidth(text, appearance.DEFAULT_FONT, size)

    def generate_toc(
        self,
        professions: Iterable[Profession],
        pages_per_sheet: int,
        count: int | None = None,
    ) -> None:
        """Build a clickable Table of Contents on page 3 (after the two cover pages).

        `count` is the per-profession roster size actually being generated (`-c`); when None each
        profession's own `number_to_generate` is used.
        """
        self.bookmark("Table of Contents")
        self.c.setFillColorRGB(0, 0, 0)
        self.c.setFont(appearance.OCR_FONT, 10)
        top = 650
        pagenum = 4  # cover, inside cover and this TOC page come first
        rows = 0
        for row, profession in enumerate(professions):
            label = profession.roster_label()
            chapter = f"{shorten(label, 37, placeholder=''):.<40}{pagenum:.>4}"
            self.c.drawString(150, top - self.line_drop(row), chapter)
            self.c.linkAbsolute(
                label,
                label,
                (145, (top - 6) - self.line_drop(row), 470, (top + 18) - self.line_drop(row)),
            )
            pagenum += (count or profession.number_to_generate) * pages_per_sheet
            rows = row + 1
        if pages_per_sheet == 1 and rows:
            # The blank back page is saved after the last character, i.e. at `pagenum`.
            chapter = f"{'Blank Character Sheet Second Page':.<40}{pagenum:.>4}"
            self.c.drawString(150, top - self.line_drop(rows), chapter)
            self.c.linkAbsolute(
                "Back Page",
                "Back Page",
                (145, (top - 6) - self.line_drop(rows), 470, (top + 18) - self.line_drop(rows)),
            )
        self.c.showPage()

    @staticmethod
    def line_drop(count: int, linesize: int = 22) -> int:
        return count * linesize

    def bookmark(self, text: str) -> None:
        self.c.bookmarkPage(text)
        self.c.addOutlineEntry(text, text)

    def draw_string(self, x: int, y: int, size: int, text: str) -> None:
        self.c.setFont(appearance.DEFAULT_FONT, size)
        self.c.setFillColorRGB(*appearance.TEXT_COLOR)
        self.c.drawString(x, y, str(text))

    def fill_field(self, field: str, value: Any) -> None:
        try:
            x, y, s = self.layout.fields[field]
        except KeyError:
            logger.error("Unknown field %s", field)  # expected condition: no traceback needed
            return
        text = str(value)
        max_width = self.layout.max_widths.get(field)
        if max_width:
            text, s = shrink_to_fit(text, s, max_width, self._measure)
        self.draw_string(x, y, s, text)

    def add_cover(self, title: str | None, oconus: bool) -> None:
        self.c.drawImage(
            str(appearance.FRONT_COVER_IMAGE), 0, 0, appearance.PAGE_WIDTH, appearance.PAGE_HEIGHT
        )
        self.c.setFillColorRGB(1, 1, 1)
        self.c.setFont(appearance.OCR_FONT, 24)
        now = datetime.now().strftime("%Y-%m-%dT%H:%MZ")
        if title:
            self.c.drawString(20, 175, title)
        self.c.drawString(20, 115, "DGGEN DTG " + now)
        self.c.drawString(20, 85, "CLASSIFIED/DG/NTK//")
        self.c.drawString(20, 55, f"SUBJ ROSTER/ACTIVE/NOCELL/{'O' if oconus else ''}CONUS//")
        self.c.drawString(20, 25, "HTTP://GITHUB.COM/JIMSTORCH/DGGEN")
        self.c.showPage()
        self.c.drawImage(
            str(appearance.INSIDE_COVER_IMAGE), 0, 0, appearance.PAGE_WIDTH, appearance.PAGE_HEIGHT
        )
        self.c.showPage()

    def _add_sheet_page(self, image: Path, fields: dict[str, FieldValue]) -> None:
        self.c.drawImage(str(image), 0, 0, appearance.PAGE_WIDTH, appearance.PAGE_HEIGHT)
        for key, value in fields.items():
            self.fill_field(key, value)
        self.c.showPage()

    def add_page(self, d: dict[str, FieldValue]) -> None:
        self._add_sheet_page(appearance.SHEET_FRONT_IMAGE, d)

    def add_page_2(self, e: dict[str, FieldValue]) -> None:
        self._add_sheet_page(appearance.SHEET_BACK_IMAGE, e)

    def add_backstory_page(self, name: str, sections: Iterable[BackstorySection]) -> None:
        """A plain page after the sheet: who the bonds are with, motivations, personal details.

        The official sheet has no room for these, so they get their own page in the sheet's
        typewriter font rather than being squeezed onto the art.
        """
        left = appearance.BACKSTORY_MARGIN
        width = appearance.PAGE_WIDTH - 2 * left
        self.c.setFillColorRGB(*appearance.TEXT_COLOR)
        self.c.setFont(appearance.OCR_FONT, 16)
        y = appearance.PAGE_HEIGHT - 72
        self.c.drawString(left, y, "BACKSTORY")
        y -= 22
        self.c.setFont(appearance.DEFAULT_FONT, 12)
        self.c.drawString(left, y, shrink_to_fit(name, 12, width, self._measure)[0])
        y -= 10
        self.c.line(left, y, left + width, y)
        y -= 30
        for section in sections:
            self.c.setFont(appearance.OCR_FONT, 12)
            self.c.drawString(left, y, section.title.upper())
            y -= 20
            self.c.setFont(appearance.DEFAULT_FONT, 11)
            for line in section.lines:
                wrapped = simpleSplit(line, appearance.DEFAULT_FONT, 11, width - 12)
                for i, piece in enumerate(wrapped):
                    if y < appearance.BACKSTORY_MARGIN:
                        logger.warning("Backstory for %s does not fit on its page", name)
                        self.c.showPage()
                        return
                    self.c.drawString(left + (12 if i else 0), y, piece)
                    y -= 15
            y -= 14
        self.c.showPage()

    def save_pdf(self) -> None:
        if self.pages_per_sheet == 1:
            self.bookmark("Back Page")
            self.c.drawImage(
                str(appearance.SHEET_BACK_IMAGE),
                0,
                0,
                appearance.PAGE_WIDTH,
                appearance.PAGE_HEIGHT,
            )
            self.c.showPage()
        self.c.save()
