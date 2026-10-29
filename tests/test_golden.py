"""Golden snapshot: the serialized d/e field dicts must stay byte-identical.

The snapshot in tests/golden/characters.json was captured from the pre-split code. This is the
safety net for the domain/serialization refactor: if the structured Character + serialize layer
change any emitted field value, this test fails.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from dggen.character import Character
from dggen.cli import get_options
from dggen.data import find_profession, load_data
from dggen.rng import Rng

GOLDEN = json.loads((Path(__file__).parent / "golden" / "characters.json").read_text("utf-8"))


def _build(prof_key: str, seed: int, veterancy: bool):
    options = get_options(["--seed", str(seed), "--pdf"])
    rng = Rng(seed)
    data = load_data(options, rng)
    prof = find_profession(data.professions, prof_key)
    char = Character.generate(
        data=data, rng=rng, sex="male", profession=prof,
        veterancy_enabled=veterancy, damaged=True,
    )
    char.equip(prof.equipment_kit)
    char.print_footnotes()
    return char


@pytest.mark.parametrize("scenario", sorted(GOLDEN))
def test_serialized_fields_match_golden(scenario):
    prof_key, seed_part, vet_part = scenario.split("|")
    char = _build(prof_key, int(seed_part.removeprefix("seed")), bool(int(vet_part.removeprefix("vet"))))
    expected = GOLDEN[scenario]
    assert char.d == expected["d"]
    assert char.e == expected["e"]
