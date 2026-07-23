"""Presentation and filesystem configuration: page geometry, colours, fonts, asset paths.

Paths are resolved relative to the installed package's data directory rather than the current
working directory, so the tool no longer has to be run from the repository root.
"""

from __future__ import annotations

import os
from pathlib import Path

# The data/ directory sits next to the package inside the repo. Allow an override via the
# DGGEN_DATA_DIR environment variable for unusual install layouts.
_DEFAULT_DATA_DIR = Path(__file__).resolve().parent.parent / "data"
DATA_DIR = Path(os.environ.get("DGGEN_DATA_DIR", _DEFAULT_DATA_DIR))

# US Letter, in points (1/72 inch). reportlab's origin is bottom-left, y increasing upward.
PAGE_WIDTH = 612
PAGE_HEIGHT = 792
PAGE_SIZE = (PAGE_WIDTH, PAGE_HEIGHT)

TEXT_COLOR = (0, 0.1, 0.5)
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

# Default data file locations, used as argparse defaults.
DEFAULT_PROFESSIONS = DATA_DIR / "professions.json"
DEFAULT_MALE_NAMES = DATA_DIR / "boys1986.txt"
DEFAULT_FEMALE_NAMES = DATA_DIR / "girls1986.txt"
DEFAULT_SURNAMES = DATA_DIR / "surnames.txt"
DEFAULT_TOWNS = DATA_DIR / "towns.txt"
DEFAULT_EQUIPMENT = DATA_DIR / "equipment.json"
DEFAULT_DISTINGUISHING = DATA_DIR / "distinguishing-features.csv"
DEFAULT_EDUCATION_DATA = DATA_DIR / "education.json"
DEFAULT_EMPLOYER_DATA = DATA_DIR / "employers.json"

DESCRIPTION = (
    "Generate characters for the Delta Green pen-and-paper roleplaying game "
    "from Arc Dream Publishing."
)
