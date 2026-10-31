"""`Rng` is the one source of randomness; its small API must keep the stdlib's exact draws.

The golden snapshot is only reproducible if each method consumes the underlying generator exactly
as the `random` call it replaced did (`choice` and `choices` in particular differ from each other
even for a uniform pick), so that equivalence is pinned here rather than assumed.
"""

from __future__ import annotations

import random

import pytest

from dggen.rng import Rng

ITEMS = ["a", "b", "c", "d", "e", "f", "g"]


@pytest.mark.parametrize("seed", range(10))
class TestMatchesTheStdlibDraw:
    def test_pick_is_choice(self, seed):
        assert Rng(seed).pick(ITEMS) == random.Random(seed).choice(ITEMS)

    def test_roll_is_randint(self, seed):
        assert Rng(seed).roll(1, 100) == random.Random(seed).randint(1, 100)

    def test_weighted_with_weights_is_choices(self, seed):
        weights = [5, 1, 1, 8, 2, 1, 3]
        expected = random.Random(seed).choices(ITEMS, weights=weights, k=1)[0]
        assert Rng(seed).weighted(ITEMS, weights) == expected

    def test_weighted_without_weights_is_uniform_choices_not_choice(self, seed):
        expected = random.Random(seed).choices(ITEMS, k=1)[0]
        assert Rng(seed).weighted(ITEMS) == expected

    def test_sample_and_shuffle(self, seed):
        assert Rng(seed).sample(ITEMS, 3) == random.Random(seed).sample(ITEMS, 3)
        mine, theirs = list(ITEMS), list(ITEMS)
        Rng(seed).shuffle(mine)
        random.Random(seed).shuffle(theirs)
        assert mine == theirs

    def test_a_sequence_of_mixed_calls_stays_in_step(self, seed):
        mine, theirs = Rng(seed), random.Random(seed)
        got = [mine.roll(1, 6), mine.pick(ITEMS), mine.weighted(ITEMS, [1] * 7), mine.roll(1, 28)]
        want = [
            theirs.randint(1, 6),
            theirs.choice(ITEMS),
            theirs.choices(ITEMS, weights=[1] * 7, k=1)[0],
            theirs.randint(1, 28),
        ]
        assert got == want


class TestTheApiIsDeliberatelyNarrow:
    @pytest.mark.parametrize("name", ["choice", "choices", "randint", "random", "uniform", "seed"])
    def test_stdlib_methods_are_not_reachable_by_accident(self, name):
        """Mixing `choice`/`choices` (or a bare `random()`) silently changes every seeded
        result; callers must use the named methods."""
        assert not hasattr(Rng(1), name)

    def test_same_seed_same_stream_different_seed_different(self):
        assert [Rng(3).roll(1, 10**6) for _ in range(1)] == [Rng(3).roll(1, 10**6)]
        assert Rng(3).roll(1, 10**9) != Rng(4).roll(1, 10**9)

    def test_unseeded_rngs_differ(self):
        assert Rng().roll(1, 10**12) != Rng().roll(1, 10**12)

    def test_bits_gives_a_seed_for_derived_generators(self):
        assert Rng(5).bits(32) == random.Random(5).getrandbits(32)
