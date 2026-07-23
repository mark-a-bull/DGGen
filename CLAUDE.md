# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

DGGen generates pre-made character sheets (as PDFs) for the Delta Green pen-and-paper RPG, following the character
creation rules from *Delta Green: Need to Know* and the *Agent's Handbook*. The logic lives in the `dggen/` package;
`data/` holds the JSON/text/CSV inputs plus font/image assets; `tests/` holds the pytest suite. `generator.py` is a
thin backwards-compatibility shim that just calls `dggen.cli.main`.

## Setup and running

```sh
python -m venv .venv
source .venv/Scripts/activate   # git-bash/WSL on Windows; .venv\Scripts\Activate.ps1 in PowerShell; .venv/bin/activate on Linux/Mac
pip install -e ".[dev]"          # editable install + dev deps (pytest, pypdf)
dggen -h                         # console entry point; or `python -m dggen -h`, or `python generator.py -h`
```

Runtime deps are `reportlab` (PDF rendering) and `faker` (optional name generation via `--names`). Dev deps
(`pytest`, `pypdf`) come from the `[dev]` extra. Because paths are resolved via `dggen/config.py` relative to the
package, the tool no longer has to be run from the repo root.

Output PDFs go to `out/` (gitignored, along with `.venv/` and `*.pdf` anywhere). `mkdir -p out/dg-veterans` is needed
once before the veteran-generation recipes in the README.

### Tests

```sh
pytest -q                                   # whole suite (fast; ~1s)
pytest tests/test_text.py::TestFormatName   # a single class
pytest -k veterancy                         # by keyword
```

Reproducibility is what makes the domain testable: all randomness flows through one seedable `dggen.rng.Rng`
(`--seed N` on the CLI). The `make_character` fixture in `tests/conftest.py` drives the whole pipeline
(`load_data` + `Character.generate`) from a single seeded `Rng`, exactly as the CLI does, so a seed reproduces a
character including its name. If you touch generation, prefer asserting on the field dicts (`character.d`/`.e`) over
rendered pixels.

`tests/test_golden.py` compares the serialized `d`/`e` for every profession × seed × veterancy against a captured
snapshot (`tests/golden/characters.json`) — the safety net for generation/serialization changes. If you *intend* to
change output, regenerate it deterministically (build characters with a seeded `Rng`, dump `d`/`e` to that JSON) and
eyeball the diff. Because the snapshot is captured in one process and checked in another, it also guards
cross-process reproducibility — beware anything whose iteration order varies by run (a bare `set()` of skill names
was one such bug).

### Verifying PDF output visually

reportlab renders text at explicit `(x, y)` point coordinates onto a background JPG — you can't judge placement from
code alone. To eyeball a change, render a page to PNG:

```python
import fitz  # PyMuPDF — NOT a project dependency; install into .venv temporarily for this only
doc = fitz.open("out/some-file.pdf")
doc[2].get_pixmap(dpi=200).save("scratch.png")  # cover=0-1, TOC (if >1 profession), then character pages
```

**Coordinate systems differ**: reportlab/PDF origin is bottom-left, y up; PyMuPDF `page`/`clip` rects are top-left,
y down. When cropping to calibrate a field with `fitz.Rect`, convert with `fitz_y = 792 - reportlab_y` (page height
792pt, US Letter). Getting this backwards silently grabs the wrong region.

## Architecture

Four layers, communicating across narrow seams. The pipeline: `cli.get_options` → `data.load_data` → for each
profession, for each character `Character.generate(...)` → `pdf.SheetWriter` draws it.

- **Data** (`models.py`, `data.py`): `@dataclass` models with `from_dict` classmethods, loaded by
  `load_data(options, rng)` into a `Data` object. `find_profession` resolves `-t/--type` by data key or display
  label (case-insensitive) and raises `ProfessionNotFound` (the CLI turns that into exit code 2 — library code
  raises, only the CLI exits). `from __future__ import annotations` in `models.py` is load-bearing: several
  `from_dict` methods return-annotate their own class, which would `NameError` under eager annotation evaluation.

- **Domain/rules** (`character.py`, `rules/`, `constants.py`, `equipped.py`): `Character` is the aggregate — typed
  generation state (`stats`, `skills`, `bonds`, derived attributes, demographics, `weapons`, …). It knows nothing
  about sheet coordinates or display formatting. `Character.generate` runs demographics → `rules.stats` →
  `rules.skills` → (default-on) `rules.education` → (optional) `rules.veterancy` → derived attributes. Each
  `rules/*` module is functions taking and mutating a `Character` (via its `.rng`); they import `Character` only
  under `TYPE_CHECKING` to avoid an import cycle. Shared game constants (stat pools, default/bonus skills) live in
  `constants.py`. `equipped.py` holds `EquippedWeapon`, the resolved per-character weapon (roll, effective damage
  modifier, assigned footnote markers) — distinct from `models.Weapon` (the raw JSON).

  `rules/education.py` auto-fills the "Education and Occupational History" field from
  `data/education.json` unless `--education` (an exact override) or `--no-education` (leave blank) is given. It
  looks up the profession by **display label**, lowercased (not the JSON key), since many different
  `professions*.json` keys across FBI/CIA/SOCOM/UK variants share one real-world label (`agent`, `cid`,
  `nsb-agent` → "Federal Agent") — same resolution style as `find_profession`. Unknown labels fall back to the
  `_default` entry. Degree phrasing (`B.S.` vs `B.A.`, `M.S.` vs `M.A.`) is chosen deterministically from the
  field name via `EducationData.science_fields`, not by a second RNG draw — this was a real bug (`M.A. Computer
  Science`) caught by hand-inspecting output before locking in the golden snapshot; if you add a new field to
  `education.json`, add it to `science_fields` too if it should take a `B.S./M.S.` degree. A tier is only eligible
  if the character is old enough (`tier.grad_age <= age`); characters younger than every eligible tier's
  `grad_age` simply get no bio rather than an error.

- **Serialization** (`serialize.py`): `to_front_fields`/`to_back_fields` turn a `Character`'s structured state into
  the `d` (front) and `e` (back/equipment) field dicts keyed by sheet field name — the *only* contract with the PDF
  layer. This is the single place that knows display formatting (checkbox `X`, `_x5` multiples, `DB=%d`, weapon
  roll/damage strings). `Character.d`/`.e` are read-only properties delegating here, so callers/tests still use
  `character.d`/`.e`. Kept reportlab-free. **RNG-ordering constraint:** anything that consumes `rng` (e.g.
  distinguishing-feature lookups) must happen during generation, not in serialization, or a fixed seed stops
  reproducing — `serialize` must be a pure function of already-generated state.

- **Presentation** (`pdf.py`): `SheetWriter` wraps a reportlab `Canvas`. `field_xys` is the single source of truth
  mapping field name → `(x, y, font_size)` on the sheet background. `fill_field` looks up each `d`/`e` key and draws
  it; unknown keys are logged and skipped, never raised (so `test_pdf.py` asserts every emitted key *has* a
  coordinate as a guard). Free-text fields that sit in a single-line box (currently just `education`, in
  `field_max_widths`) run through `text.shrink_to_fit`, which shrinks font size then ellipsis-truncates — reuse this
  for any new free-text field.

- **Interface** (`cli.py`, `logging_setup.py`, `config.py`): argparse + the generation loop; `config.py` centralises
  page geometry, colours, fonts, and all asset/data paths.

**Pure helpers** (`text.py`) — `parse_date`, `format_name`, `age_on`, `generate_label`, `shrink_to_fit` — are
reportlab/faker-free and are the cheapest, highest-value things to unit test. `shrink_to_fit` takes a `measure`
callback so it stays pure; `pdf.py` passes the reportlab width function.

**Profession data files** (`data/professions*.json`, e.g. `-fbi`, `-cia`, `-dea`, `-socom`, `-uk`) are swappable via
`--professions`; each is `key → {label, number_to_generate, skills, bonds, equipment-kit, employer, division}`.
Adding a profession set means adding a JSON file, not touching code.

## Key CLI flags

- `-t/--type` — profession key or display label (case-insensitive); unknown values list every valid key/label pair.
- Single specific character: `-t` + `-c 1` + any of `--name`, `--sex`, `--birth-year`, `--birthdate` (precedence over
  `--birth-year`; also sets the exact birthday shown), `--employer`, `--education`.
- Education/occupational history is auto-generated by default (age- and profession-appropriate degree +
  institution); `--education "..."` overrides it exactly, `--no-education` leaves it blank instead.
- `--seed N` — reproducible output (same seed + options ⇒ identical characters).
- `--veterancy` / `--no-damaged` / `-a`/`-A` — veteran rules (skill boosts, stat losses, Damaged Veteran effects,
  AH p.38).
- Full reference: `dggen -h` and the "Customising" section of README.md.
