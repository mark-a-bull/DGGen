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
                                                      weights it is still the `choices` draw;
                                                      `cum_weights=` takes running totals)
- `roll(low, high)`        an int in [low, high]      (`random.randint`)
- `sample(seq, k)`         k distinct elements        (`random.sample`)
- `shuffle(items)`         in place                   (`random.shuffle`)
- `bits(k)`                k random bits, e.g. to seed a derived generator (`random.getrandbits`)
- `fork()`                 a new `Rng` derived from this one's current state, *without* drawing from
                          it (so adding a consumer of the fork never moves anyone else's draws)

`tests/test_rng.py` pins each of these to the stdlib call it wraps.
"""

from __future__ import annotations

import hashlib
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

    def weighted(
        self,
        values: Sequence[T],
        weights: Sequence[float] | None = None,
        *,
        cum_weights: Sequence[float] | None = None,
    ) -> T:
        """One element, by relative `weights` or by precomputed running totals `cum_weights`
        (the same draw; use the latter to avoid re-summing a very long list on every call)."""
        return self._random.choices(values, weights=weights, cum_weights=cum_weights, k=1)[0]

    def roll(self, low: int, high: int) -> int:
        return self._random.randint(low, high)

    def sample(self, population: Sequence[T], k: int) -> list[T]:
        return self._random.sample(population, k)

    def shuffle(self, items: MutableSequence[T]) -> None:
        self._random.shuffle(items)

    def bits(self, k: int) -> int:
        return self._random.getrandbits(k)

    def fork(self) -> Rng:
        """A new generator seeded from a hash of this one's current state; this one is not advanced.

        Use it for an optional extra that should not disturb the main stream: whether it runs or
        not, every later draw from `self` is the same. The fork is a pure function of the state, so
        the same seed still reproduces it (in any process), and forks taken at different points
        differ."""
        digest = hashlib.sha256(repr(self._random.getstate()).encode()).digest()
        return Rng(int.from_bytes(digest[:8], "big"))
