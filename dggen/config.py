"""Filesystem configuration: where the data lives and the default data files.

Paths are resolved relative to the installed package's data directory rather than the current
working directory, so the tool no longer has to be run from the repository root. How the sheet
looks (page size, fonts, images) is `dggen.appearance`.
"""

from __future__ import annotations

import os
from pathlib import Path

# The data directory is a subpackage-style folder inside the package (dggen/data/), so it ships
# in the wheel and resolves the same way for editable and installed copies. Allow an override via
# the DGGEN_DATA_DIR environment variable for unusual install layouts.
_DEFAULT_DATA_DIR = Path(__file__).resolve().parent / "data"
DATA_DIR = Path(os.environ.get("DGGEN_DATA_DIR", _DEFAULT_DATA_DIR))

# Flat/weighted value-list pools live under here (dggen/pools.py auto-discovers every file).
# Adding a value to an existing category, or a whole new one, never requires touching code -
# see dggen/data/pools/README.md.
POOLS_DIR = DATA_DIR / "pools"

# Default data file locations, used as argparse defaults.
DEFAULT_PROFESSIONS = DATA_DIR / "professions.json"
DEFAULT_EQUIPMENT = DATA_DIR / "equipment.json"
DEFAULT_DISTINGUISHING = DATA_DIR / "distinguishing-features.csv"
DEFAULT_SHEET_LAYOUT = DATA_DIR / "sheet-layout.json"
DEFAULT_EDUCATION_DATA = DATA_DIR / "education.json"
DEFAULT_EMPLOYER_DATA = DATA_DIR / "employers.json"

# Default pool ids (not file paths) for the auto-generated name/town providers - resolved
# against Pools, which also accepts an arbitrary file path here instead of an id (e.g.
# --towns /my/custom-towns.csv), for a completely custom list living outside dggen/data/pools/.
DEFAULT_MALE_NAMES = "names/male-given"
DEFAULT_FEMALE_NAMES = "names/female-given"
DEFAULT_SURNAMES = "names/surnames"
DEFAULT_TOWNS = "towns/us"

DESCRIPTION = (
    "Generate characters for the Delta Green pen-and-paper roleplaying game "
    "from Arc Dream Publishing."
)
