# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

DGGen generates pre-made character sheets (as PDFs) for the Delta Green pen-and-paper RPG, following the character
creation rules from *Delta Green: Need to Know* and the *Agent's Handbook*. The logic lives in the `dggen/` package;
`dggen/data/` holds the structured JSON/CSV config plus font/image assets, `dggen/data/pools/` holds flat value lists (see
below), and `tests/` holds the pytest suite. `generator.py` is a thin backwards-compatibility shim that just calls
`dggen.cli.main`.

**Packaging:** the data lives *inside* the package (`dggen/data/`) and is declared under
`[tool.setuptools.package-data]` in `pyproject.toml`; non-Python files outside a package, or not listed there, are
silently left out of the wheel and an installed copy then fails with `FileNotFoundError` (editable installs and the
test suite would never notice). `tests/test_packaging.py` builds a real wheel and checks every asset `dggen.config`
points at is in it. Only the reference PDFs (`dggen/data/*.pdf`) are deliberately excluded — if you add a new kind of
runtime file under `dggen/data/`, that test is what tells you whether it ships.

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
character including its name. If you touch generation, prefer asserting on the field dicts (`serialize.to_front_fields(char)` / `to_back_fields(char)`) over
rendered pixels.

`tests/test_golden.py` compares the serialized `d`/`e` for every profession × seed × veterancy against a captured
snapshot (`tests/golden/characters.json`) — the safety net for generation/serialization changes. If you *intend* to
change output, regenerate it deterministically (build characters with a seeded `Rng`, dump `d`/`e` to that JSON),
eyeball a sample of the diff by hand (not just that it changed, but that the new values are sensible), and lock it
in. Because the snapshot is captured in one process and checked in another, it also guards cross-process
reproducibility — beware anything whose iteration order varies by run (a bare `set()` of skill names was one such
bug). Also beware `random.Random.choice()` vs `.choices()`: they consume the RNG differently and return different
results for an identical seed even when picking from the same list uniformly, so swapping one for the other is a
golden-changing move in its own right, not a no-op refactor (this is why `Pools.choice()` — see below — standardises
on `.choices()` everywhere, rather than "no observable behavior change").

### Types

`dggen/` is kept clean under `mypy --strict` (config in `pyproject.toml`; `mypy` and `types-reportlab` are in the
`[dev]` extra). `tests/test_typing.py` runs it — on the package, and on `tests/` with the untyped-def rules relaxed
because fixtures and test functions are deliberately unannotated — so a type error fails the suite. Run `mypy` on its
own for the full message. What the types encode, so you don't have to rediscover it: `Character.profession` is
required at construction (never `None`); `char.skills` is all `int`, with sub-skill names split into
`char.skill_labels`; sheet fields are `serialize.FieldValue` (`str | int`); `store_footnote` takes and returns `str`.

### Style

`ruff` handles linting and formatting (config in `pyproject.toml`: line length 100, rule set listed there; `ruff` is in
the `[dev]` extra). `tests/test_style.py` runs `ruff check` and `ruff format --check`, so both fail the suite when
violated. To fix: `ruff check --fix dggen tests generator.py` for the auto-fixable rules and
`ruff format dggen tests generator.py` for layout. Line endings are pinned to LF by `.gitattributes` /
`.editorconfig`, independent of each contributor's `core.autocrlf`. Imports go at the top of the module (including in
tests); exception classes end in `Error`. `--min-age` defaults to 25 on the CLI but `Character.generate(min_age=...)`
defaults to 24 — left alone because unifying them changes every seeded character and the golden snapshot with it.

### Security notes

- **Templates in data files** (`{city}` in `employers.json`, `{field}`/`{institution}`/`{year}` in `education.json`)
  are filled by `text.fill_template`, never `str.format`: data files are swappable (`--employer-data`,
  `--education-data`), and `str.format` would let a template reach attributes (`{city.__class__}`) or crash with a
  bare `KeyError`. Only plain `{name}` placeholders (and `{{`/`}}`) are accepted; `EducationTier.from_dict` and
  `EmployerOption.from_dict` validate every template when the file is loaded, so a bad one exits 2 at startup via
  `TemplateError` instead of failing mid-roster. If you add a placeholder, add it to `EDUCATION_TEMPLATE_FIELDS` /
  `EMPLOYER_TEMPLATE_FIELDS` in `models.py` and pass it from the rule module.
- **Dependency floors** matter because reportlab only asks for `pillow>=9`: `pyproject.toml` floors Pillow at 13.0.0
  (it needs Python 3.11+, hence the `python_version` marker; 3.10 gets the newest Pillow it can install) and the dev
  extra floors `pypdf`. Check with `pip-audit` (install it somewhere throwaway; it isn't a project dependency):
  `pip-audit -r requirements.txt`. `tests/test_packaging.py` fails if the Pillow floor is dropped from either
  `pyproject.toml` or `requirements.txt`.

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

- **Data** (`models.py`, `data.py`, `pools.py`): `@dataclass` models with `from_dict` classmethods, loaded by
  `load_data(options, rng)` into a `Data` object. `find_profession` resolves `-t/--type` by data key or display
  label (case-insensitive) and raises `ProfessionNotFoundError` (the CLI turns that into exit code 2 — library code
  raises, only the CLI exits). `from __future__ import annotations` in `models.py` is load-bearing: several
  `from_dict` methods return-annotate their own class, which would `NameError` under eager annotation evaluation.

  **Value pools** (`pools.py`, `dggen/data/pools/`): every flat/weighted value list DGGen draws from at random — given
  names, surnames, towns, employer names, institution names, which fields count as "science" for degree phrasing —
  lives under `dggen/data/pools/` as one `.txt` (flat list) or `.csv` (optional weight column) file per category, auto-
  discovered by `Pools` at `load_data()` time. A pool's id is its path under `dggen/data/pools/` minus the extension (e.g.
  `employers/federal-law`). Structured config (`education.json`, `employers.json`, and the `--male-given-names`/
  `--female-given-names`/`--surnames`/`--towns` CLI flags) reference pool ids as plain strings rather than embedding
  the lists inline — this is deliberate: it's the boundary between "just add a line to a text file" (no code-shape
  knowledge needed, `dggen/data/pools/README.md` is the whole contract) and "understand the wiring" (which profession
  draws from which pool, with what weights). `Pools.choice()`/`.values()` also accept an arbitrary file path instead
  of a registered id, so `--towns /my/custom-towns.csv` still works for a list that isn't checked into the repo.

- **Domain/rules** (`character.py`, `rules/`, `constants.py`, `equipped.py`): `Character` is the aggregate — typed
  generation state (`stats`, `skills`, `bonds`, derived attributes, demographics, `town`, `weapons`, …). It knows
  nothing about sheet coordinates or display formatting. `Character.generate` runs demographics → (default-on)
  `rules.employer` → `rules.stats` → `rules.skills` → (default-on) `rules.education` → (optional)
  `rules.veterancy` → derived attributes. Each `rules/*` module is functions taking and mutating a `Character`
  (via its `.rng`); they import `Character` only under `TYPE_CHECKING` to avoid an import cycle. Shared game
  constants (stat pools, default/bonus skills) live in `constants.py`. `equipped.py` holds `EquippedWeapon`, the
  resolved per-character weapon (roll, effective damage modifier, assigned footnote markers) — distinct from
  `models.Weapon` (the raw JSON).

  The profession JSON stores sub-skill names as `<base>label` strings next to a `<base>value` score
  (`craft1label: "Electrician"`, `craft1value: 40`), because that is how the sheet lays them out. Generation splits
  them: scores go in `char.skills` (always `int`, safe for arithmetic), names in `char.skill_labels`; `serialize`
  merges both back for the sheet and `text._skill_rows` folds each pair into one "Craft (Electrician)" row. Veterancy experience checks apply only to fixed skills, the `possible` skills
  actually picked (`char.picked_skills`) and `char.bonus_skills` — an unpicked `possible` skill is just a default
  skill. Bonus skills are de-duplicated before picking, so a profession-suggested bonus is never boosted twice.

  `rules/education.py` and `rules/employer.py` both auto-fill a sheet field from a JSON data file (`education.json`,
  `employers.json`) unless an explicit override (`--education`/`--employer`) or a "don't" flag
  (`--no-education`/`--no-employer`) is given, and both look up the profession by **display label**, lowercased
  (not the JSON key), since many different `professions*.json` keys across FBI/CIA/SOCOM/UK variants share one
  real-world label (`agent`, `cid`, `nsb-agent` → "Federal Agent") — same resolution style as `find_profession`.
  Unknown labels fall back to each file's `_default` entry.

  `-t` by display label can match several professions (`cid` and `nsb-agent` are both "Federal Agent" in the FBI set):
  `find_profession` takes an exact key first (case-insensitively), then the first label match, and `main` prints a
  note to stderr naming the alternatives (`data.ambiguous_keys`). Equipment kits must fit the sheet's 7 weapon slots
  (Unarmed takes one) and 22 gear lines; overflow is dropped with a warning naming what was lost, and
  `test_every_bundled_kit_fits_the_weapon_slots` fails if a kit *always* overflows (as the SWAT grenades once did).
  Footnote markers are handed out in first-use order; past the 14 available the last one is shared, with a warning.

  `rules/education.py`: degree phrasing (`B.S.` vs `B.A.`, `M.S.` vs `M.A.`) is chosen deterministically from the
  field name via the pool at `EducationData.science_fields_pool` (default `fields/science`), not by a second RNG
  draw — this was a real bug (`M.A. Computer Science`) caught by hand-inspecting output before locking in the golden
  snapshot; if you add a new field to `education.json`, add it to `dggen/data/pools/fields/science.txt` too if it should
  take a `B.S./M.S.` degree. Institution names come from `char.data.pools.choice(pool_id, char.rng)`, where
  `pool_id` is `tier.institution_pool` (e.g. `institutions/university`) unless the profession's
  `institution_pool_overrides` swaps in something more specific for that tier (e.g. a firefighter's `academy` tier
  overrides to `institutions/fire-academy` rather than the generic `institutions/military-basic`). A tier is only
  eligible if the character is old enough (`tier.grad_age <= age`); characters younger than every eligible tier's
  `grad_age` simply get no bio rather than an error.

  `rules/employer.py`: only fills `char.employer` if it's still blank after demographics — i.e. neither
  `--employer` nor the profession's own `employer`/`division` (hardcoded in variant files like
  `professions-fbi.json`, e.g. `"FBI, CID"`) provided one, so those must never be clobbered. Each profession in
  `employers.json` maps to a weighted list of options, each either a `pool` (a pool id, e.g.
  `employers/federal-law`, resolved via `char.data.pools.choice(...)`), a `template` with `{city}` (resolved against
  `char.town`, e.g. `"{city} Police Department"`), or a fixed `literal` (e.g. `"U.S. Navy"`). `char.town` is the raw
  town string set in `generate_demographics` (`char.nationality` is `f"({nationality}) " + char.town`, not the
  other way around — read `char.town`, not a parsed-back `char.nationality`, if you need just the city).

- **Serialization** (`serialize.py`): `to_front_fields`/`to_back_fields` turn a `Character`'s structured state into
  the `d` (front) and `e` (back/equipment) field dicts keyed by sheet field name — the *only* contract with the PDF
  layer. This is the single place that knows display formatting (checkbox `X`, `_x5` multiples, `DB=%d`, weapon
  roll/damage strings). The dependency runs one way: `serialize` imports `Character`, never the reverse, so call
  `to_front_fields(char)` rather than looking for a property on the character. Kept reportlab-free. **RNG-ordering constraint:** anything that consumes `rng` (e.g.
  distinguishing-feature lookups) must happen during generation, not in serialization, or a fixed seed stops
  reproducing — `serialize` must be a pure function of already-generated state.

- **Pool errors** (`pools.py`): `PoolError` is the base the CLI catches; `UnknownPoolError` means no such id/file and
  `InvalidPoolError` means the file is unusable (empty, non-integer/negative/all-zero weights, a row missing its weight, a
  third column — usually an unquoted comma —, or not UTF-8). All are raised when the file is read, i.e. at startup, with
  the file and line in the message. A UTF-8 BOM is tolerated.

- **Presentation** (`pdf.py`): `SheetWriter` wraps a reportlab `Canvas`. `field_xys` is the single source of truth
  mapping field name → `(x, y, font_size)` on the sheet background. `fill_field` looks up each `d`/`e` key and draws
  it; unknown keys are logged and skipped, never raised (so `test_pdf.py` asserts every emitted key *has* a
  coordinate as a guard). Free-text fields that sit in a single-line box (`name`, `profession`, `employer`,
  `nationality`, `education` and the seven weapon names, in `field_max_widths`) run through `text.shrink_to_fit`,
  which shrinks font size then ellipsis-truncates — reuse this for any new free-text field. Weapon names are drawn in
  full and shrunk (never cut at a fixed length, which made "Grenade launcher" and "Grenade machine gun" identical).

- **Library entry points** (`options.py`, `roster.py`, `sinks.py`, `summary.py`): `DataSources` /
  `GenerationOptions` are plain frozen dataclasses (no argparse) taken by `load_data` and `Character.generate`;
  `roster.generate_roster(data, rng, professions, options, count=, sex=, equip=)` lazily yields
  `(profession, character)` with each character already equipped and its footnotes flushed (use
  `generate_character` rather than repeating generate → equip → `print_footnotes`); `sinks.TextSink` / `PdfSink`
  consume them through four methods (`begin`, `start_profession`, `add`, `finish`), so a new output format is one
  more class. `summary.py` renders the text view; `Profession.roster_label()` gives the roster/bookmark label.

- **Interface** (`cli.py`, `logging_setup.py`, `config.py`): argparse (`build_parser` describes the flags,
  `validate_options` holds the cross-flag rules, `get_options` does both, `sources_from` / `generation_from` build
  the option dataclasses) + `main`, which wires roster → sinks; `config.py` centralises
  page geometry, colours, fonts, and all asset/data paths.

**Pure helpers** (`text.py`) — `parse_date`, `format_name`, `age_on`, `fill_template`, `shrink_to_fit` — are
reportlab/faker-free and are the cheapest, highest-value things to unit test. `shrink_to_fit` takes a `measure`
callback so it stays pure; `pdf.py` passes the reportlab width function.

**Profession data files** (`dggen/data/professions*.json`, e.g. `-fbi`, `-cia`, `-dea`, `-socom`, `-uk`) are swappable via
`--professions`; each is `key → {label, number_to_generate, skills, bonds, equipment-kit, employer, division}`.
Adding a profession set means adding a JSON file, not touching code.

## Key CLI flags

- **Default output is plain text, not a PDF.** Every generated character is printed as a readable summary
  (`dggen.summary.format_details`) to stdout. Pass `--pdf` to also write a PDF via `-o/--output`, which restores the
  historical behavior: without `-t`, every profession's full roster (`number_to_generate` characters each) is
  generated. Without `--pdf`, `-t/--type` is required (argparse errors otherwise) and `-c/--count` defaults to `1`
  instead of the profession's roster size — this mode is for previewing one character's stats/skills/equipment
  quickly, not for bulk PDF rosters.
- Bad input is rejected up front, not mid-run: `get_options` raises a usage error (exit 2) for `-c` below 1,
  `-a` above `-A` or negative, and a `--pdf -o` directory that doesn't exist; `main` returns 2 (no traceback) for a
  missing data file, bad JSON, an unknown `--names` Faker locale, an unknown profession or an unknown pool.
  `main` also switches stdout to `errors="replace"` so a non-Latin name can't abort a run on a legacy console.
- `generate_toc` takes the effective `-c` so TOC page numbers match the bookmarks (cover + inside cover + TOC come
  first, so the first character is on page 4); `tests/test_pdf.py` checks them against the PDF's real outline.
- `-t/--type` — profession key or display label (case-insensitive); unknown values list every valid key/label pair.
- Single specific character: `-t` + `-c 1` + any of `--name`, `--sex`, `--birth-year`, `--birthdate` (precedence over
  `--birth-year`; also sets the exact birthday shown), `--employer`, `--education`.
- Education/occupational history is auto-generated by default (age- and profession-appropriate degree +
  institution); `--education "..."` overrides it exactly, `--no-education` leaves it blank instead.
- Employer is auto-generated by default for professions without one hardcoded in the profession data
  (age-irrelevant, but town-aware for local roles like police/fire); `--employer "..."` overrides it exactly,
  `--no-employer` leaves it blank instead.
- `--seed N` — reproducible output (same seed + options ⇒ identical characters).
- `--veterancy` / `--no-damaged` / `-a`/`-A` — veteran rules (skill boosts, stat losses, Damaged Veteran effects,
  AH p.38).
- `--male-given-names`/`--female-given-names`/`--surnames`/`--towns` take a pool id (e.g. `towns/uk` for the bundled
  UK list) or a path to your own file; `--distinguishing-features`/`--professions`/`--equipment`/`--education-data`/
  `--employer-data` remain plain file paths (structured config, not pools).
- Full reference: `dggen -h` and the "Customising" section of README.md.
