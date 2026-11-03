"""Shared fixtures: a loaded `Data` object and a seeded character factory."""

from __future__ import annotations

import pytest

from dggen.character import Character
from dggen.data import find_profession, load_data
from dggen.options import DataSources, GenerationOptions
from dggen.rng import Rng


@pytest.fixture
def data():
    """Real Data loaded from the bundled data files (it holds no randomness)."""
    return load_data(DataSources())


@pytest.fixture
def make_character():
    """Factory: build a fully deterministic Character at a given seed.

    One `Rng(seed)` drives generation, including the name and town draws, as the CLI does, so the
    same seed reproduces the whole character.
    """

    def _make(profession="agent", seed=1234, sex="male", **kwargs):
        rng = Rng(seed)
        loaded = load_data(DataSources())
        prof = find_profession(loaded.professions, profession)
        return Character.generate(
            data=loaded,
            rng=rng,
            sex=sex,
            profession=prof,
            options=GenerationOptions(**kwargs),
        )

    return _make
