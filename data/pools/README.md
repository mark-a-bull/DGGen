# Value pools

Everything in this directory is a plain list of values — names, towns, employers, schools, and
so on. **You don't need to know anything about the code to add to one of these.**

## Adding a value

Open the relevant file and add a line. That's it.

- `data/pools/employers/fictional-companies.txt` — add a company name your criminal or engineer
  characters might work for.
- `data/pools/institutions/university.txt` — add a college.
- `data/pools/names/male-given.txt` — add a first name.

Blank lines and lines starting with `#` are ignored, so a file can carry a one-line comment at
the top explaining what it's for.

## Adding a whole new list

Drop a new `.txt` file into an existing folder (or a new folder). It's usable immediately, by an
id equal to its path without the folder or the extension — e.g. a new file at
`data/pools/employers/private-security.txt` is the pool `employers/private-security`.

Having the values available isn't the same as a profession *using* them — that wiring (which
profession draws from which pool, and how often) lives in `data/employers.json` and
`data/education.json`, and does require understanding their structure. If you just want to expand
an *existing* pool that's already wired up, you don't need to touch those files at all.

## File formats

- **`.txt`** — one value per line. This is almost every file here.
- **`.csv`** — use this only if a value needs a companion number, like a town's population (so
  bigger cities come up more often). First column is the value, second column (optional) is an
  integer weight. A `.csv` with just one column behaves exactly like a `.txt` file.

## What's *not* here

`data/distinguishing-features.csv` (which trait a character gets for a given stat range) and the
profession/equipment/education/employer JSON files aren't value pools — they're structured
configuration that reference the pools here by id. Those do require understanding their shape;
see `CLAUDE.md` if you're changing them.
