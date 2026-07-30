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

# Flat/weighted value-list pools live under here (dggen/pools.py auto-discovers every file).
# Adding a value to an existing category, or a whole new one, never requires touching code -
# see data/pools/README.md.
POOLS_DIR = DATA_DIR / "pools"

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
DEFAULT_EQUIPMENT = DATA_DIR / "equipment.json"
DEFAULT_DISTINGUISHING = DATA_DIR / "distinguishing-features.csv"
DEFAULT_EDUCATION_DATA = DATA_DIR / "education.json"
DEFAULT_EMPLOYER_DATA = DATA_DIR / "employers.json"

# Default pool ids (not file paths) for the auto-generated name/town providers - resolved
# against Pools, which also accepts an arbitrary file path here instead of an id (e.g.
# --towns /my/custom-towns.csv), for a completely custom list living outside data/pools/.
DEFAULT_MALE_NAMES = "names/male-given"
DEFAULT_FEMALE_NAMES = "names/female-given"
DEFAULT_SURNAMES = "names/surnames"
DEFAULT_TOWNS = "towns/us"

DESCRIPTION = (
    "Generate characters for the Delta Green pen-and-paper roleplaying game "
    "from Arc Dream Publishing."
)
