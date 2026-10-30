"""Cross-references in the data files are checked when the data loads, not mid-roster."""

from __future__ import annotations

import json
import logging
from dataclasses import replace

import pytest

from dggen import config
from dggen.cli import main
from dggen.data import load_data
from dggen.models import EmployerOption, EmployerProfession, WeaponRef
from dggen.options import DataSources
from dggen.rng import Rng
from dggen.validate import DataError, validate_data


def test_every_bundled_profession_set_validates():
    for path in sorted(config.DATA_DIR.glob("professions*.json")):
        data = load_data(DataSources(professions=path), Rng(0))
        validate_data(data)  # raises DataError on any dangling reference


class TestEducationReferences:
    def test_unknown_institution_pool(self, data):
        data.education.tier_defaults["bachelors"].institution_pool = "institutions/nowhere"
        with pytest.raises(DataError, match=r"bachelors.*institutions/nowhere"):
            validate_data(data)

    def test_unknown_science_fields_pool(self, data):
        data.education.science_fields_pool = "fields/nope"
        with pytest.raises(DataError, match="fields/nope"):
            validate_data(data)

    def test_profession_names_a_tier_that_does_not_exist(self, data):
        data.education.professions["_default"].tiers["doctorate-ish"] = 1
        with pytest.raises(DataError, match="doctorate-ish"):
            validate_data(data)

    def test_override_for_an_unknown_pool_or_tier(self, data):
        overrides = data.education.professions["_default"].institution_pool_overrides
        overrides["academy"] = "institutions/nowhere"
        overrides["no-such-tier"] = "institutions/university"
        with pytest.raises(DataError) as exc:
            validate_data(data)
        assert "institutions/nowhere" in str(exc.value)
        assert "no-such-tier" in str(exc.value)

    def test_missing_default_profession(self, data):
        del data.education.professions["_default"]
        with pytest.raises(DataError, match="_default"):
            validate_data(data)


class TestEmployerReferences:
    def test_unknown_pool(self, data):
        data.employer.professions["pilot"] = EmployerProfession(
            options=[EmployerOption(pool="employers/nowhere")]
        )
        with pytest.raises(DataError, match=r"pilot.*employers/nowhere"):
            validate_data(data)

    def test_missing_default_profession(self, data):
        del data.employer.professions["_default"]
        with pytest.raises(DataError, match="_default"):
            validate_data(data)


class TestEquipmentReferences:
    def test_profession_names_a_kit_that_does_not_exist(self, data):
        key = next(iter(data.professions))
        data.professions[key] = replace(data.professions[key], equipment_kit="no-such-kit")
        with pytest.raises(DataError, match=rf"{key}.*no-such-kit"):
            validate_data(data)

    def test_kit_names_a_weapon_that_does_not_exist(self, data):
        data.kits["agent"].weapons.append(WeaponRef(type="plasma-rifle"))
        with pytest.raises(DataError, match=r"agent.*plasma-rifle"):
            validate_data(data)

    def test_nested_weapon_references_are_checked_too(self, data):
        data.kits["agent"].weapons.append(
            WeaponRef(one_of=[WeaponRef(both=[WeaponRef(type="ray-gun")])])
        )
        with pytest.raises(DataError, match="ray-gun"):
            validate_data(data)

    def test_kit_names_armour_that_does_not_exist(self, data):
        data.kits["agent"].armour[0].type = "force-field"
        with pytest.raises(DataError, match="force-field"):
            validate_data(data)

    def test_the_unarmed_weapon_must_exist(self, data):
        del data.weapons["unarmed"]
        with pytest.raises(DataError, match="unarmed"):
            validate_data(data)


def test_every_problem_is_reported_in_one_error(data):
    data.education.science_fields_pool = "fields/nope"
    data.kits["agent"].weapons.append(WeaponRef(type="plasma-rifle"))
    with pytest.raises(DataError) as exc:
        validate_data(data)
    message = str(exc.value)
    assert "fields/nope" in message
    assert "plasma-rifle" in message
    assert "2 problems" in message


def test_valid_data_is_accepted(data):
    validate_data(data)


class TestFromTheCommandLine:
    def test_a_dangling_reference_exits_2(self, tmp_path):
        source = json.loads(config.DEFAULT_EDUCATION_DATA.read_text("utf-8"))
        source["science_fields_pool"] = "fields/nope"
        path = tmp_path / "education.json"
        path.write_text(json.dumps(source), encoding="utf-8")
        assert main(["-t", "agent", "--education-data", str(path)]) == 2

    def test_a_missing_key_names_the_file_instead_of_a_bare_keyerror(self, tmp_path, caplog):
        path = tmp_path / "professions.json"
        path.write_text(json.dumps({"x": {"label": "X"}}), encoding="utf-8")
        with caplog.at_level(logging.ERROR, logger="dggen"):
            assert main(["-t", "x", "--professions", str(path)]) == 2
        assert "professions.json" in caplog.text
        assert "number_to_generate" in caplog.text  # says which key is missing
