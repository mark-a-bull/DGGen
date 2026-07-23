"""Presentation layer: draw the field dicts onto the Delta Green character sheet PDF.

`field_xys` is the single source of truth mapping a field name to its `(x, y, font_size)` on the
sheet background image. The domain layer produces dicts keyed by these names; `SheetWriter` looks
each key up and draws it. Unknown keys are logged and skipped, never raised.
"""

from __future__ import annotations

import logging
from datetime import datetime
from textwrap import shorten
from typing import TYPE_CHECKING, Any

from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas

from dggen import config
from dggen.text import generate_label, shrink_to_fit

if TYPE_CHECKING:
    from collections.abc import Iterable
    from pathlib import Path

    from dggen.models import Profession

logger = logging.getLogger("dggen")


class SheetWriter:
    # Location of form fields in points (1/72 inch); origin 0,0 is bottom-left. (x, y, font size)
    field_xys = {
        # Personal Data
        "name": (75, 693, 11),
        "profession": (343, 693, 11),
        "employer": (75, 665, 11),
        "nationality": (343, 665, 11),
        "education": (268, 640, 11),
        "age": (185, 640, 11),
        "birthday": (200, 640, 11),
        "male": (98, 639, 11),
        "female": (76, 639, 11),
        # Statistical Data
        "strength": (136, 604, 11),
        "constitution": (136, 586, 11),
        "dexterity": (136, 568, 11),
        "intelligence": (136, 550, 11),
        "power": (136, 532, 11),
        "charisma": (136, 514, 11),
        "strength_x5": (172, 604, 11),
        "constitution_x5": (172, 586, 11),
        "dexterity_x5": (172, 568, 11),
        "intelligence_x5": (172, 550, 11),
        "power_x5": (172, 532, 11),
        "charisma_x5": (172, 514, 11),
        "strength_distinguishing": (208, 604, 11),
        "constitution_distinguishing": (208, 586, 11),
        "dexterity_distinguishing": (208, 568, 11),
        "intelligence_distinguishing": (208, 550, 11),
        "power_distinguishing": (208, 532, 11),
        "charisma_distinguishing": (208, 514, 11),
        "damage bonus": (555, 200, 11),
        "hitpoints": (195, 482, 11),
        "willpower": (195, 464, 11),
        "sanity": (195, 446, 11),
        "current_sanity": (265, 446, 11),
        "breaking point": (195, 428, 11),
        "bond0": (512, 604, 11),
        "bond1": (512, 586, 11),
        "bond2": (512, 568, 11),
        "bond3": (512, 550, 11),
        "disorder0": (340, 482, 11),
        "violence": (372, 384, 10),
        "helplessness": (486, 384, 10),
        # Applicable Skill Sets
        "accounting": (200, 361, 11),
        "alertness": (200, 343, 11),
        "anthropology": (200, 325, 11),
        "archeology": (200, 307, 11),
        "art1": (200, 289, 11),
        "art2": (200, 281, 11),
        "artillery": (200, 253, 11),
        "athletics": (200, 235, 11),
        "bureaucracy": (200, 217, 11),
        "computer science": (200, 200, 11),
        "craft1label": (90, 185, 9),
        "craft1value": (200, 185, 9),
        "craft2label": (90, 177, 9),
        "craft2value": (200, 177, 9),
        "craft3label": (90, 169, 9),
        "craft3value": (200, 169, 9),
        "craft4label": (90, 161, 9),
        "craft4value": (200, 161, 9),
        "criminology": (200, 145, 11),
        "demolitions": (200, 127, 11),
        "disguise": (200, 109, 11),
        "dodge": (200, 91, 11),
        "drive": (200, 73, 11),
        "firearms": (200, 54, 11),
        "first aid": (361, 361, 11),
        "forensics": (361, 343, 11),
        "heavy machinery": (361, 325, 11),
        "heavy weapons": (361, 307, 11),
        "history": (361, 289, 11),
        "humint": (361, 270, 11),
        "law": (361, 253, 11),
        "medicine": (361, 235, 11),
        "melee weapons": (361, 217, 11),
        "militaryscience1value": (361, 199, 11),
        "militaryscience1label": (327, 199, 11),
        "militaryscience2value": (361, 186, 11),
        "militaryscience2label": (327, 186, 11),
        "navigate": (361, 163, 11),
        "occult": (361, 145, 11),
        "persuade": (361, 127, 11),
        "pharmacy": (361, 109, 11),
        "pilot1value": (361, 91, 9),
        "pilot1label": (290, 91, 9),
        "pilot2value": (361, 83, 9),
        "pilot2label": (290, 83, 9),
        "psychotherapy": (361, 54, 11),
        "ride": (521, 361, 11),
        "science1label": (442, 347, 9),
        "science1value": (521, 347, 9),
        "science2label": (442, 340, 9),
        "science2value": (521, 340, 9),
        "science3label": (442, 333, 9),
        "science3value": (521, 333, 9),
        "science4label": (442, 326, 9),
        "science4value": (521, 326, 9),
        "search": (521, 307, 11),
        "sigint": (521, 289, 11),
        "stealth": (521, 270, 11),
        "surgery": (521, 253, 11),
        "survival": (521, 235, 11),
        "swim": (521, 217, 11),
        "unarmed combat": (521, 200, 11),
        "unnatural": (521, 181, 11),
        "language1": (521, 145, 11),
        "language2": (521, 127, 11),
        "language3": (521, 109, 11),
        "skill1": (521, 91, 11),
        "skill2": (521, 73, 11),
        "skill3": (521, 54, 11),
        # 2nd page
        "weapon0": (85, 480, 11),
        "weapon0_roll": (175, 480, 11),
        "weapon0_range": (215, 480, 11),
        "weapon0_damage": (270, 480, 11),
        "weapon0_ap": (345, 480, 11),
        "weapon0_lethality": (410, 480, 11),
        "weapon0_kill_radius": (462, 480, 11),
        "weapon0_ammo": (525, 480, 11),
        "weapon0_note": (560, 480, 11),
        "weapon1": (85, 461, 11),
        "weapon1_roll": (175, 461, 11),
        "weapon1_range": (215, 461, 11),
        "weapon1_damage": (270, 461, 11),
        "weapon1_ap": (345, 461, 11),
        "weapon1_lethality": (410, 461, 11),
        "weapon1_kill_radius": (462, 461, 11),
        "weapon1_ammo": (525, 461, 11),
        "weapon1_note": (560, 461, 11),
        "weapon2": (85, 442, 11),
        "weapon2_roll": (175, 442, 11),
        "weapon2_range": (215, 442, 11),
        "weapon2_damage": (270, 442, 11),
        "weapon2_ap": (345, 442, 11),
        "weapon2_lethality": (410, 442, 11),
        "weapon2_kill_radius": (462, 442, 11),
        "weapon2_ammo": (525, 442, 11),
        "weapon2_note": (560, 442, 11),
        "weapon3": (85, 423, 11),
        "weapon3_roll": (175, 423, 11),
        "weapon3_range": (215, 423, 11),
        "weapon3_damage": (270, 423, 11),
        "weapon3_ap": (345, 423, 11),
        "weapon3_lethality": (410, 423, 11),
        "weapon3_kill_radius": (462, 423, 11),
        "weapon3_ammo": (525, 423, 11),
        "weapon3_note": (560, 423, 11),
        "weapon4": (85, 404, 11),
        "weapon4_roll": (175, 404, 11),
        "weapon4_range": (215, 404, 11),
        "weapon4_damage": (270, 404, 11),
        "weapon4_ap": (345, 404, 11),
        "weapon4_lethality": (410, 404, 11),
        "weapon4_kill_radius": (462, 404, 11),
        "weapon4_ammo": (525, 404, 11),
        "weapon4_note": (560, 404, 11),
        "weapon5": (85, 385, 11),
        "weapon5_roll": (175, 385, 11),
        "weapon5_range": (215, 385, 11),
        "weapon5_damage": (270, 385, 11),
        "weapon5_ap": (345, 385, 11),
        "weapon5_lethality": (410, 385, 11),
        "weapon5_kill_radius": (462, 385, 11),
        "weapon5_ammo": (525, 385, 11),
        "weapon5_note": (560, 385, 11),
        "weapon6": (85, 366, 11),
        "weapon6_roll": (175, 366, 11),
        "weapon6_range": (215, 366, 11),
        "weapon6_damage": (270, 366, 11),
        "weapon6_ap": (345, 366, 11),
        "weapon6_lethality": (410, 366, 11),
        "weapon6_kill_radius": (465, 366, 11),
        "weapon6_ammo": (525, 366, 11),
        "weapon6_note": (560, 366, 11),
        "gear0": (75, 628, 8),
        "gear1": (75, 618, 8),
        "gear2": (75, 608, 8),
        "gear3": (75, 598, 8),
        "gear4": (75, 588, 8),
        "gear5": (75, 578, 8),
        "gear6": (75, 568, 8),
        "gear7": (75, 558, 8),
        "gear8": (75, 548, 8),
        "gear9": (75, 538, 8),
        "gear10": (75, 528, 8),
        "gear11": (323, 628, 8),
        "gear12": (323, 618, 8),
        "gear13": (323, 608, 8),
        "gear14": (323, 598, 8),
        "gear15": (323, 588, 8),
        "gear16": (323, 578, 8),
        "gear17": (323, 568, 8),
        "gear18": (323, 558, 8),
        "gear19": (323, 548, 8),
        "gear20": (323, 538, 8),
        "gear21": (323, 528, 8),
        "note0": (50, 40, 8),
        "note1": (50, 30, 8),
        "note2": (50, 20, 8),
        "note3": (50, 10, 8),
        "note4": (240, 40, 8),
        "note5": (240, 30, 8),
        "note6": (240, 20, 8),
        "note7": (240, 10, 8),
        "note8": (410, 40, 8),
        "note9": (410, 30, 8),
        "note10": (410, 20, 8),
        "note11": (410, 10, 8),
        "detail0": (75, 338, 8),
        "detail1": (75, 328, 8),
        "detail2": (75, 318, 8),
        "detail3": (75, 308, 8),
        "detail4": (75, 298, 8),
        "detail5": (75, 288, 8),
    }

    # Fields whose value must be shrunk (and, failing that, truncated) to fit within this many
    # points, since they sit in a single-line box rather than wrapping to a new page area.
    field_max_widths = {"education": 260}

    def __init__(self, filename: Path, pages_per_sheet: int = 1) -> None:
        self.filename = filename
        self.pages_per_sheet = pages_per_sheet
        self.c = canvas.Canvas(str(self.filename))
        self.c.setPageSize(config.PAGE_SIZE)
        self.c.setAuthor("https://github.com/jimstorch/DGGen")
        self.c.setTitle("Delta Green Agent Roster")
        self.c.setSubject("Pre-generated characters for the Delta Green RPG")
        pdfmetrics.registerFont(TTFont(config.DEFAULT_FONT, str(config.DEFAULT_FONT_FILE)))
        pdfmetrics.registerFont(TTFont(config.OCR_FONT, str(config.OCR_FONT_FILE)))

    def _measure(self, text: str, size: int) -> float:
        return pdfmetrics.stringWidth(text, config.DEFAULT_FONT, size)

    def generate_toc(self, professions: Iterable[Profession], pages_per_sheet: int) -> None:
        """Build a clickable Table of Contents on page 1."""
        self.bookmark("Table of Contents")
        self.c.setFillColorRGB(0, 0, 0)
        self.c.setFont(config.OCR_FONT, 10)
        top = 650
        pagenum = 2
        profession = None
        for count, profession in enumerate(professions):
            label = generate_label(profession)
            chapter = "{:.<40}".format(shorten(label, 37, placeholder="")) + f"{pagenum:.>4}"
            self.c.drawString(150, top - self.line_drop(count), chapter)
            self.c.linkAbsolute(
                label,
                label,
                (145, (top - 6) - self.line_drop(count), 470, (top + 18) - self.line_drop(count)),
            )
            pagenum += profession.number_to_generate * pages_per_sheet
        if pages_per_sheet == 1 and profession is not None:
            chapter = (
                "{:.<40}".format("Blank Character Sheet Second Page")
                + f"{pagenum + profession.number_to_generate:.>4}"
            )
            self.c.drawString(150, top - self.line_drop(pagenum), chapter)
            self.c.linkAbsolute(
                "Back Page",
                "Back Page",
                (145, (top - 6) - self.line_drop(pagenum), 470, (top + 18) - self.line_drop(pagenum)),
            )
        self.c.showPage()

    @staticmethod
    def line_drop(count: int, linesize: int = 22) -> int:
        return count * linesize

    def bookmark(self, text: str) -> None:
        self.c.bookmarkPage(text)
        self.c.addOutlineEntry(text, text)

    def draw_string(self, x: int, y: int, size: int, text: str) -> None:
        self.c.setFont(config.DEFAULT_FONT, size)
        self.c.setFillColorRGB(*config.TEXT_COLOR)
        self.c.drawString(x, y, str(text))

    def fill_field(self, field: str, value: Any) -> None:
        try:
            x, y, s = self.field_xys[field]
        except KeyError:
            logger.exception("Unknown field %s", field)
            return
        text = str(value)
        max_width = self.field_max_widths.get(field)
        if max_width:
            text, s = shrink_to_fit(text, s, max_width, self._measure)
        self.draw_string(x, y, s, text)

    def add_cover(self, title: str, oconus: bool) -> None:
        self.c.drawImage(str(config.FRONT_COVER_IMAGE), 0, 0, config.PAGE_WIDTH, config.PAGE_HEIGHT)
        self.c.setFillColorRGB(255, 255, 255)
        self.c.setFont(config.OCR_FONT, 24)
        now = datetime.now().strftime("%Y-%m-%dT%H:%MZ")
        if title:
            self.c.drawString(20, 175, title)
        self.c.drawString(20, 115, "DGGEN DTG " + now)
        self.c.drawString(20, 85, "CLASSIFIED/DG/NTK//")
        self.c.drawString(20, 55, f"SUBJ ROSTER/ACTIVE/NOCELL/{'O' if oconus else ''}CONUS//")
        self.c.drawString(20, 25, "HTTP://GITHUB.COM/JIMSTORCH/DGGEN")
        self.c.showPage()
        self.c.drawImage(str(config.INSIDE_COVER_IMAGE), 0, 0, config.PAGE_WIDTH, config.PAGE_HEIGHT)
        self.c.showPage()

    def add_page(self, d: dict[str, Any]) -> None:
        self.c.drawImage(str(config.SHEET_FRONT_IMAGE), 0, 0, config.PAGE_WIDTH, config.PAGE_HEIGHT)
        for key in d:
            self.fill_field(key, d[key])
        self.c.showPage()

    def add_page_2(self, e: dict[str, Any]) -> None:
        self.c.drawImage(str(config.SHEET_BACK_IMAGE), 0, 0, config.PAGE_WIDTH, config.PAGE_HEIGHT)
        for key in e:
            self.fill_field(key, e[key])
        self.c.showPage()

    def save_pdf(self) -> None:
        if self.pages_per_sheet == 1:
            self.bookmark("Back Page")
            self.c.drawImage(
                str(config.SHEET_BACK_IMAGE), 0, 0, config.PAGE_WIDTH, config.PAGE_HEIGHT,
            )
            self.c.showPage()
        self.c.save()
