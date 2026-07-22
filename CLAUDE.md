# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

DGGen is a single-script Python CLI (`generator.py`) that generates pre-made character sheets (as PDFs) for the
Delta Green pen-and-paper RPG, following the character creation rules from *Delta Green: Need to Know* and the
*Agent's Handbook*. There is no package structure, build step, or test suite — it's one ~1500-line script plus a
`data/` directory of JSON/text/CSV inputs and font/image assets.

## Setup and running

```sh
python -m venv .venv
source .venv/Scripts/activate   # git-bash/WSL on Windows; use .venv\Scripts\Activate.ps1 in PowerShell, or .venv/bin/activate on Linux/Mac
pip install -U -r requirements.txt
python generator.py -h
```

Dependencies are just `reportlab` (PDF rendering) and `faker` (optional name generation via `--names`). There is no
lint config, formatter config, or test suite in this repo — verify changes by actually running the generator and
inspecting output, not by looking for a `pytest`/`ruff` invocation that doesn't exist.

Output PDFs go to `out/` (gitignored, along with `.venv/` and `*.pdf` anywhere). `mkdir -p out/dg-veterans` is needed
once before running the veteran-generation recipes in the README.

### Verifying PDF output visually

reportlab renders text at explicit `(x, y)` point coordinates onto a background JPG/PDF — there's no way to inspect
correctness from the code alone. To check a change actually looks right on the sheet, render a page to a PNG and
view it:

```python
import fitz  # PyMuPDF — not a project dependency, install into .venv temporarily for this only
doc = fitz.open("out/some-file.pdf")
doc[2].get_pixmap(dpi=200).save("scratch.png")  # page index varies: cover=0-1, TOC (if >1 profession), then characters
```

**Coordinate systems differ**: reportlab/PDF space has origin bottom-left with y increasing upward; PyMuPDF's
`page`/`clip` rects use origin top-left with y increasing downward. When calibrating a new field position by
cropping with `fitz.Rect`, convert with `fitz_y = 792 - reportlab_y` (page height is 792pt, standard Letter).
Getting this backwards silently grabs the wrong region of the page.

## Architecture

Everything lives in `generator.py`, structured as one linear pipeline:

`get_options()` (argparse) → `load_data()` → for each profession, for each character: build a `Need2KnowCharacter`
→ `Need2KnowPDF` draws it onto the output PDF.

**Data layer** (`Data`, `Profession`, `ProfessionSkills`, `Kit`, `KitGearEntry`, `KitArmourEntry`, `Weapon`,
`WeaponRef`, `Damage`, `Lethality` — all `@dataclass` with a `from_dict()` classmethod): loaded once by `load_data()`
from `data/professions.json` (or an alternate file passed via `--professions`), `data/equipment.json`, name/town
text files, and `data/distinguishing-features.csv`. `from __future__ import annotations` at the top of the file is
load-bearing, not cosmetic — several `from_dict()` methods return-annotate with their own not-yet-fully-defined
class (e.g. `ProfessionSkills.from_dict` returning `-> ProfessionSkills`), which raises `NameError` at import time
without deferred annotation evaluation.

**Character generation** (`Need2KnowCharacter`): one instance per generated character. `__init__` runs
`generate_demographics` → `generate_stats` → `generate_skills` → (optionally) `veterancy` → `generate_derived_attributes`,
then optionally `equip()`. All sheet values accumulate into two plain dicts: `self.d` (front page fields) and
`self.e` (back/equipment page fields, only populated if the character is equipped) — these dicts are exactly what
gets handed to the PDF-drawing layer, keyed by field name.

Overrides for a specific character (name, sex, birth year/date, employer, education, label) are plumbed as
constructor parameters through `generate_demographics`, applied *after* the random default is computed, so a
partially-specified character (e.g. profession + name only) still gets randomized stats/skills/age as normal.
`format_name()` normalizes free-text `--name` input into the sheet's `SURNAME, Given` convention unless the input
already contains a comma. `find_profession()` resolves `-t/--type` against either a profession's data key or its
display label, case-insensitively.

**Rendering** (`Need2KnowPDF`): wraps a reportlab `Canvas`. `field_xys` is the single source of truth mapping a
field name to its `(x, y, font_size)` position on the character sheet background image
(`data/Character Sheet NO BACKGROUND FRONT.jpg`, drawn full-bleed at 612×792pt = US Letter). `fill_field()` looks up
each key in `self.d`/`self.e` against `field_xys` and draws it; unknown keys are logged and skipped rather than
raising. Fields expected to hold variable-length free text in a single-line box (currently just `education`) are
listed in `field_max_widths` and run through `shrink_to_fit()`, which reduces font size and then truncates with an
ellipsis rather than letting text run off the page — this pattern should be reused for any new free-text field
rather than assuming short input.

**Profession data files** (`data/professions*.json`) are swappable via `--professions` — e.g.
`data/professions-fbi.json`, `-cia.json`, `-dea.json`, `-socom.json`, `-uk.json` — each defining the same
key→`{label, number_to_generate, skills, bonds, equipment-kit, employer, division}` shape. Adding a new profession
set means adding a new JSON file in that shape, not touching `generator.py`.

## Key CLI flags worth knowing about

- `-t/--type` accepts a profession key or its display label (case-insensitive); invalid values print every valid
  key/label pair.
- Single-character generation: combine `-t` with `-c 1` and any of `--name`, `--sex`, `--birth-year`,
  `--birthdate` (takes precedence over `--birth-year` and sets the exact birthday shown, not just the age),
  `--employer`, `--education`.
- `--veterancy` / `--no-damaged` / `-a`/`-A` control the veteran-generation rules (skill boosts, stat losses,
  Damaged Veteran effects per AH p.38).
- Full flag reference: `python generator.py -h`, and the "Customising" section of README.md.
