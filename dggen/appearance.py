"""How the character sheet looks: page geometry, colours, fonts, and the background images.

Presentation constants only. Where the data lives (and the default data files) is `dggen.config`;
where each field is drawn is the sheet layout (`dggen.layout`). The font and image files are
resolved from the same data directory.
"""

from __future__ import annotations

from dggen.config import DATA_DIR

# US Letter, in points (1/72 inch). reportlab's origin is bottom-left, y increasing upward.
PAGE_WIDTH = 612
PAGE_HEIGHT = 792
PAGE_SIZE = (PAGE_WIDTH, PAGE_HEIGHT)

TEXT_COLOR = (0, 0.1, 0.5)
# Left/right/bottom margin of the plain backstory page that follows each character's sheet.
BACKSTORY_MARGIN = 56

DEFAULT_FONT = "Special Elite"
OCR_FONT = "OCRA"

# Font files (registered with reportlab at render time).
DEFAULT_FONT_FILE = DATA_DIR / "SpecialElite.ttf"
OCR_FONT_FILE = DATA_DIR / "OCRA.ttf"

# Full-bleed background images.
FRONT_COVER_IMAGE = DATA_DIR / "front_cover.jpg"
INSIDE_COVER_IMAGE = DATA_DIR / "inside_cover.jpg"
SHEET_FRONT_IMAGE = DATA_DIR / "Character Sheet NO BACKGROUND FRONT.jpg"
SHEET_BACK_IMAGE = DATA_DIR / "Character Sheet NO BACKGROUND BACK.jpg"
