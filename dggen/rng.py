"""A single, seedable source of randomness for the whole generator.

Threading one `Rng` through generation (instead of the global `random` module) makes output
reproducible: construct `Rng(seed)` and the same seed yields the same characters, which is what
lets the domain layer be tested by asserting on concrete output. An unseeded `Rng()` is
nondeterministic.

The API is deliberately small and does *not* expose the stdlib's methods. Each method below
consumes the underlying generator exactly as the named `random` call does, and that matters:
`random.choice()` and `random.choices()` draw differently and give different results for the same
seed even when picking uniformly from the same list. Swapping one for the other silently changes
every seeded character (and the golden snapshot), so callers must say which one they mean:

- `pick(seq)`             one uniform element        (`random.choice`)
- `weighted(seq, weights)` one weighted element       (`random.choices(..., k=1)[0]`; with no
                                                      weights it is still the `choices` draw)
- `roll(low, high)`        an int in [low, high]      (`random.randint`)
- `sample(seq, k)`         k distinct elements        (`random.sample`)
- `shuffle(items)`         in place                   (`random.shuffle`)
- `bits(k)`                k random bits, e.g. to seed a derived generator (`random.getrandbits`)

`tests/test_rng.py` pins each of these to the stdlib call it wraps.
"""

from __future__ import annotations

import random
from typing import TYPE_CHECKING, TypeVar

if TYPE_CHECKING:
    from collections.abc import MutableSequence, Sequence

T = TypeVar("T")


class Rng:
    """Seedable RNG. `Rng(None)` (the default) is nondeterministic; `Rng(1234)` is repeatable."""

    def __init__(self, seed: int | None = None) -> None:
        self._random = random.Random(seed)

    def pick(self, seq: Sequence[T]) -> T:
        return self._random.choice(seq)

    def weighted(self, values: Sequence[T], weights: Sequence[float] | None = None) -> T:
        return self._random.choices(values, weights=weights, k=1)[0]

    def roll(self, low: int, high: int) -> int:
        return self._random.randint(low, high)

    def sample(self, population: Sequence[T], k: int) -> list[T]:
        return self._random.sample(population, k)

    def shuffle(self, items: MutableSequence[T]) -> None:
        self._random.shuffle(items)

    def bits(self, k: int) -> int:
        return self._random.getrandbits(k)
