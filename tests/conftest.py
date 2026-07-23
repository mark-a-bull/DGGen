"""Shared fixtures: a loaded `Data` object and a seeded character factory."""

from __future__ import annotations

import pytest

from dggen.cli import get_options
from dggen.data import find_profession, load_data
from dggen.rng import Rng


@pytest.fixture
def data():
    """Real Data loaded from the bundled data files, using a seeded RNG for its providers."""
    options = get_options(["--seed", "0"])
    return load_data(options, Rng(0))


@pytest.fixture
def make_character():
    """Factory: build a fully deterministic Character at a given seed.

    A single `Rng(seed)` drives both data loading (name/town providers) and generation, exactly
    as the CLI does, so the same seed reproduces the whole character including its name.
    """
    from dggen.character import Character

    def _make(profession="agent", seed=1234, sex="male", **kwargs):
        options = get_options(["--seed", str(seed)])
        rng = Rng(seed)
        loaded = load_data(options, rng)
        prof = find_profession(loaded.professions, profession)
        return Character.generate(
            data=loaded, rng=rng, sex=sex, profession=prof, **kwargs,
        )

    return _make
