"""`Rng` is the one source of randomness; its small API must keep the stdlib's exact draws.

The golden snapshot is only reproducible if each method consumes the underlying generator exactly
as the `random` call it replaced did (`choice` and `choices` in particular differ from each other
even for a uniform pick), so that equivalence is pinned here rather than assumed.
"""

from __future__ import annotations

import random
from itertools import accumulate

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


class TestFork:
    """`fork()` gives an optional extra its own stream without moving anyone else's draws."""

    @pytest.mark.parametrize("seed", range(5))
    def test_forking_does_not_advance_the_parent(self, seed):
        forked, untouched = Rng(seed), Rng(seed)
        forked.fork()
        forked.fork()
        assert [forked.roll(1, 10**9) for _ in range(5)] == [
            untouched.roll(1, 10**9) for _ in range(5)
        ]

    @pytest.mark.parametrize("seed", range(5))
    def test_drawing_from_a_fork_does_not_move_the_parent(self, seed):
        forked, untouched = Rng(seed), Rng(seed)
        child = forked.fork()
        for _ in range(100):
            child.roll(1, 100)
        assert forked.roll(1, 10**9) == untouched.roll(1, 10**9)

    def test_the_same_state_gives_the_same_fork(self):
        first, second = Rng(5).fork(), Rng(5).fork()
        assert [first.roll(1, 10**9) for _ in range(5)] == [second.roll(1, 10**9) for _ in range(5)]

    def test_forks_taken_at_different_points_differ(self):
        rng = Rng(5)
        early = rng.fork()
        rng.roll(1, 100)
        late = rng.fork()
        assert [early.roll(1, 10**9) for _ in range(5)] != [late.roll(1, 10**9) for _ in range(5)]

    def test_a_fork_is_not_a_copy_of_the_parent_stream(self):
        parent = Rng(5)
        child = parent.fork()
        assert [child.roll(1, 10**9) for _ in range(5)] != [parent.roll(1, 10**9) for _ in range(5)]

    def test_the_fork_of_a_seed_is_the_same_in_every_process(self):
        """Pinned values: a hash of the state, so nothing here may depend on this process (a
        `hash()` of a str or an object id would pass every in-process test and fail this)."""
        zero, other = Rng(0).fork(), Rng(12345).fork()
        assert [zero.roll(1, 10**6) for _ in range(3)] == [694639, 15101, 561131]
        assert [other.roll(1, 10**6) for _ in range(3)] == [318786, 233689, 576659]

    def test_an_unseeded_rng_forks_too(self):
        assert isinstance(Rng().fork().roll(1, 6), int)


@pytest.mark.parametrize("seed", range(10))
class TestCumulativeWeights:
    """`cum_weights` lets a caller precompute the running totals once (the towns pool has 25,000
    entries); it must draw exactly as the relative `weights` form does."""

    WEIGHTS = (5, 1, 1, 8, 2, 1, 3)

    def test_matches_the_stdlib_and_the_relative_form(self, seed):
        cum = list(accumulate(self.WEIGHTS))
        expected = random.Random(seed).choices(ITEMS, cum_weights=cum, k=1)[0]
        assert Rng(seed).weighted(ITEMS, cum_weights=cum) == expected
        assert Rng(seed).weighted(ITEMS, self.WEIGHTS) == expected

    def test_giving_both_forms_is_an_error_as_in_the_stdlib(self, seed):
        with pytest.raises(TypeError):
            Rng(seed).weighted(ITEMS, [1] * 7, cum_weights=[1, 2, 3, 4, 5, 6, 7])
