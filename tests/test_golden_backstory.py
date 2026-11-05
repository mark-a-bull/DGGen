"""Golden snapshot of the backstories: named bonds, motivations and personal details.

`test_golden.py` and `test_golden_variants.py` hold the sheet fields (`d`/`e`), which the backstory
does not touch, so nothing else pins what it produces. This does: the same seed must give the same
bonds, motivations and details in every process, which a same-process "twice gives the same" check
cannot show (a bare `set()` or a changed draw order would pass that and fail this).

If you *intend* to change the backstory (a pool line, the draw order, how a bond is named),
regenerate `tests/golden/backstories.json` with `snapshot()` below for every row of `SCENARIOS`
(`json.dumps(..., indent=1, sort_keys=True)`), then read the diff: names should still match the
relationship's sex, family bonds should share the character's surname, and a veteran should only
have people for the bonds it kept. Editing a bundled pool file changes this snapshot by design.
"""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from typing import Any

import pytest

from dggen.data import load_data
from dggen.options import DataSources, GenerationOptions
from dggen.rng import Rng
from dggen.roster import generate_character

GOLDEN = json.loads((Path(__file__).parent / "golden" / "backstories.json").read_text("utf-8"))

TODAY = date(2026, 6, 1)  # pinned like the other snapshots, so veteran ages never drift

# key: (profession, seed, sex, options). The key is what the snapshot file is indexed by.
SCENARIOS: dict[str, tuple[str, int, str, dict[str, Any]]] = {
    "agent-1-male": ("agent", 1, "male", {}),
    "agent-2-female": ("agent", 2, "female", {}),
    "nurse-3-female": ("nurse", 3, "female", {}),
    "soldier-4-male": ("soldier", 4, "male", {}),
    "police-5-male": ("police", 5, "male", {}),
    "scientist-6-female": ("scientist", 6, "female", {}),
    "pilot-7-male": ("pilot", 7, "male", {}),
    "veteran-soldier-8": ("soldier", 8, "male", {"veterancy_enabled": True}),
    "veteran-nurse-9": ("nurse", 9, "female", {"veterancy_enabled": True}),
    "veteran-that-lost-a-bond": ("agent", 4, "male", {"veterancy_enabled": True}),
    "named-with-a-suffix": ("agent", 11, "male", {"name_override": "Kim Smith Jr."}),
}


def snapshot(profession: str, seed: int, sex: str, options: dict[str, Any]) -> dict[str, Any]:
    data = load_data(DataSources())
    char = generate_character(
        data,
        Rng(seed),
        sex,
        data.professions[profession],
        GenerationOptions(today=TODAY, **options),
    )
    story = char.backstory
    assert story is not None
    return {
        "name": char.name,
        "bonds": [[b.slot, b.relationship, b.name, b.score] for b in story.bonds],
        "motivations": list(story.motivations),
        "personal_details": list(story.personal_details),
    }


def test_every_scenario_has_a_snapshot_and_vice_versa():
    assert sorted(GOLDEN) == sorted(SCENARIOS)


@pytest.mark.parametrize("scenario", sorted(SCENARIOS))
def test_backstory_matches_its_snapshot(scenario):
    assert snapshot(*SCENARIOS[scenario]) == GOLDEN[scenario]


def test_the_lost_bond_scenario_really_loses_a_bond():
    """Positive control: otherwise the scenario would pass while testing nothing."""
    profession, seed, sex, options = SCENARIOS["veteran-that-lost-a-bond"]
    data = load_data(DataSources())
    char = generate_character(
        data,
        Rng(seed),
        sex,
        data.professions[profession],
        GenerationOptions(today=TODAY, **options),
    )
    assert len(char.bonds) < char.profession.bonds
    assert char.backstory is not None
    assert len(char.backstory.bonds) == len(char.bonds)
