"""Auto-discovered value-list pools: drop a file under data/pools/, reference its id from a
config file (or a CLI flag), done. No code changes needed to add a value or a whole new list.

A pool's id is its path under the pools root, without extension, with forward slashes -
e.g. `data/pools/employers/federal-law.txt` is `employers/federal-law`. Two formats are
understood, chosen by extension:

- `.txt` - one value per line. Blank lines and lines starting with `#` are ignored, so a file can
  document itself. Every value is equally likely.
- `.csv` - like `.txt`, but a second column is treated as an integer weight (e.g. town population),
  making later rows proportionally more likely. A `.csv` with only one column behaves exactly
  like a `.txt` list. The header row is always skipped.

Callers pass either a discovered pool's id, or a path to an arbitrary file elsewhere on disk (for
`--towns /my/custom/list.csv`-style overrides) - `Pools` resolves whichever it's given the same
way, and caches the result.
"""

from __future__ import annotations

import csv
import itertools
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from dggen.rng import Rng

_POOL_EXTENSIONS = (".txt", ".csv")


class UnknownPool(Exception):
    """Raised when a pool id/path matches neither a discovered pool nor an existing file."""

    def __init__(self, ref: str, available_ids: list[str]) -> None:
        super().__init__(
            f"Unknown pool {ref!r}. It isn't a discovered pool id, and isn't a file that "
            f"exists on disk. Available pool ids: {', '.join(available_ids)}",
        )
        self.ref = ref


class Pools:
    def __init__(self, root: Path) -> None:
        self._root = root
        self._cache: dict[str, tuple[list[str], list[int] | None]] = {}
        if root.is_dir():
            for path in sorted(root.rglob("*")):
                if path.is_file() and path.suffix in _POOL_EXTENSIONS:
                    pool_id = path.relative_to(root).with_suffix("").as_posix()
                    self._cache[pool_id] = _read_pool_file(path)

    def ids(self) -> list[str]:
        return sorted(self._cache)

    def _resolve(self, ref: str) -> tuple[list[str], list[int] | None]:
        if ref in self._cache:
            return self._cache[ref]
        path = Path(ref)
        if path.is_file() and path.suffix in _POOL_EXTENSIONS:
            resolved = _read_pool_file(path)
            self._cache[ref] = resolved  # cache ad hoc external files too
            return resolved
        raise UnknownPool(ref, self.ids())

    def validate(self, ref: str) -> None:
        """Raise UnknownPool immediately if `ref` won't resolve, rather than waiting until the
        first (possibly deep into generation) `choice()`/`values()` call that needs it."""
        self._resolve(ref)

    def values(self, ref: str) -> list[str]:
        """The pool's values, in file order, ignoring any weights."""
        values, _weights = self._resolve(ref)
        return values

    def choice(self, ref: str, rng: Rng) -> str:
        """One random value, weighted if the pool has weights, uniform otherwise."""
        values, weights = self._resolve(ref)
        cum_weights = list(itertools.accumulate(weights)) if weights else None
        return rng.choices(values, cum_weights=cum_weights, k=1)[0]


def _read_pool_file(path: Path) -> tuple[list[str], list[int] | None]:
    if path.suffix == ".csv":
        return _read_csv_pool(path)
    return _read_txt_pool(path), None


def _read_txt_pool(path: Path) -> list[str]:
    lines = path.read_text(encoding="utf-8").splitlines()
    return [line.strip() for line in lines if line.strip() and not line.startswith("#")]


def _read_csv_pool(path: Path) -> tuple[list[str], list[int] | None]:
    with path.open(encoding="utf-8", newline="") as f:
        rows = [row for row in csv.reader(f) if row]
    rows = rows[1:]  # header
    values = [row[0] for row in rows]
    weights = [int(row[1]) for row in rows] if rows and len(rows[0]) > 1 else None
    return values, weights
