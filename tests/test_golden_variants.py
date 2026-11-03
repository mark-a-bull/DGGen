"""Golden snapshot, part two: the options and data sets `test_golden.py` doesn't reach.

`test_golden.py` covers male characters, default ages and the default profession file. This adds
female characters, exact birthdates and birth years, unequipped sheets, every override and switch,
veterans with and without damage, and each of the other profession files (with the UK town list
for the UK set). The snapshot is `tests/golden/variants.json`; the scenarios are the table below,
so adding one means adding a row and regenerating (and reading) the diff, as for the main snapshot.

`today` is pinned, because ages and graduation years are measured against it.
"""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from typing import Any

import pytest

from dggen import config
from dggen.data import find_profession, load_data
from dggen.options import DataSources, GenerationOptions
from dggen.rng import Rng
from dggen.roster import generate_character
from dggen.serialize import to_back_fields, to_front_fields

TODAY = date(2026, 6, 1)
GOLDEN = json.loads((Path(__file__).parent / "golden" / "variants.json").read_text("utf-8"))

# name -> how to build it. `professions`/`towns` choose the data; `options` is GenerationOptions.
SCENARIOS: dict[str, dict[str, Any]] = {
    # who they are
    "female-agent": {"profession": "agent", "sex": "female", "seed": 11},
    "female-nurse-veteran": {
        "profession": "nurse",
        "sex": "female",
        "seed": 12,
        "options": {"veterancy_enabled": True},
    },
    "exact-birthdate-physician": {
        "profession": "physician",
        "seed": 13,
        "options": {"birthdate": date(1975, 3, 14)},
    },
    "birth-year-pilot": {"profession": "pilot", "seed": 14, "options": {"birth_year": 1988}},
    "age-range-engineer": {
        "profession": "engineer",
        "seed": 15,
        "options": {"min_age": 40, "max_age": 45},
    },
    # veterans
    "veteran-undamaged-soldier": {
        "profession": "soldier",
        "seed": 16,
        "options": {"veterancy_enabled": True, "damaged": False, "birthdate": date(1960, 5, 5)},
    },
    # seed 16 is one where the 20% damage roll lands: a disorder, lost sanity, adaptations
    "veteran-damaged-spec-ops": {
        "profession": "spec-ops",
        "seed": 16,
        "options": {"veterancy_enabled": True, "damaged": True, "birthdate": date(1955, 9, 9)},
    },
    # overrides and switches
    "every-override": {
        "profession": "lawyer",
        "seed": 18,
        "options": {
            "name_override": "Dr. Ada Quill",
            "label_override": "Counsel",
            "employer_override": "Quill & Co",
            "education_override": "LL.M. Nowhere 2001",
            "nationality": "U.K.",
        },
    },
    "no-employer-no-education": {
        "profession": "agent",
        "seed": 19,
        "options": {"auto_employer": False, "auto_education": False},
    },
    "unequipped-police": {"profession": "police", "seed": 20, "equip": False},
    # the other profession sets
    "fbi-cid": {"profession": "cid", "seed": 21, "professions": "professions-fbi.json"},
    "fbi-swat-kit": {"profession": "hrt", "seed": 22, "professions": "professions-fbi.json"},
    "cia-case-officer": {
        "profession": "do-case-officer",
        "seed": 23,
        "professions": "professions-cia.json",
    },
    "cia-sagsod": {"profession": "sagsod", "seed": 24, "professions": "professions-cia.json"},
    "dea-agent": {"profession": "agent", "seed": 25, "professions": "professions-dea.json"},
    "socom-seal": {"profession": "seal", "seed": 26, "professions": "professions-socom.json"},
    "uk-case-officer": {
        "profession": "mi6-case-officer",
        "seed": 27,
        "professions": "professions-uk.json",
        "towns": "towns/uk",
        "options": {"nationality": "U.K."},
    },
    "uk-sas": {
        "profession": "22-sas",
        "seed": 28,
        "professions": "professions-uk.json",
        "towns": "towns/uk",
        "options": {"veterancy_enabled": True},
    },
}


def build(spec: dict[str, Any]) -> dict[str, Any]:
    sources = DataSources(
        professions=config.DATA_DIR / spec.get("professions", "professions.json"),
        towns=spec.get("towns", config.DEFAULT_TOWNS),
    )
    data = load_data(sources)
    profession = find_profession(data.professions, spec["profession"])
    options = GenerationOptions(today=TODAY, **spec.get("options", {}))
    char = generate_character(
        data,
        Rng(spec["seed"]),
        spec.get("sex", "male"),
        profession,
        options,
        equip=spec.get("equip", True),
    )
    return {"d": to_front_fields(char), "e": to_back_fields(char)}


def test_every_scenario_has_a_snapshot_and_vice_versa():
    assert set(GOLDEN) == set(SCENARIOS)


@pytest.mark.parametrize("name", sorted(SCENARIOS))
def test_scenario_matches_its_snapshot(name):
    assert build(SCENARIOS[name]) == GOLDEN[name]
