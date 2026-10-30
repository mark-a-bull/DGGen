"""Unit tests for dataclass from_dict parsing (hyphenated keys, defaults)."""

from __future__ import annotations

import dataclasses
import typing

import pytest

from dggen import models
from dggen.models import (
    Damage,
    EducationData,
    EducationTier,
    EmployerData,
    EmployerOption,
    Kit,
    Profession,
    ProfessionSkills,
    Weapon,
)
from dggen.text import TemplateError


def test_profession_skills_defaults():
    skills = ProfessionSkills.from_dict({"fixed": {"anthropology": 50}})
    assert skills.fixed == {"anthropology": 50}
    assert skills.possible == {}
    assert skills.possible_count == 0
    assert skills.bonus == []


def test_profession_skills_maps_hyphenated_possible_count():
    skills = ProfessionSkills.from_dict(
        {"fixed": {}, "possible": {"ride": 50}, "possible-count": 2, "bonus": ["occult"]},
    )
    assert skills.possible_count == 2
    assert skills.bonus == ["occult"]


def test_profession_maps_equipment_kit_and_optional_fields():
    prof = Profession.from_dict(
        {
            "label": "Anthropologist",
            "number_to_generate": 30,
            "skills": {"fixed": {"anthropology": 50}},
            "bonds": 4,
            "equipment-kit": "civilian",
        },
    )
    assert prof.label == "Anthropologist"
    assert prof.equipment_kit == "civilian"
    assert prof.employer == ""  # default when absent


def test_weapon_maps_hyphenated_keys_and_nested_damage():
    weapon = Weapon.from_dict(
        {
            "name": "Pistol",
            "skill": "firearms",
            "base-range": "15m",
            "damage": {"dice": 1, "die-type": 10, "db-applies": True},
            "ammo": 15,
        },
    )
    assert weapon.base_range == "15m"
    assert weapon.ammo == 15
    assert weapon.damage is not None
    assert weapon.damage.dice == 1
    assert weapon.damage.die_type == 10
    assert weapon.damage.db_applies is True


def test_kit_defaults_gear_to_empty():
    kit = Kit.from_dict({"weapons": [], "armour": []})
    assert kit.gear == []


def test_education_data_from_dict():
    education = EducationData.from_dict(
        {
            "tier_defaults": {
                "bachelors": {
                    "grad_age": 22,
                    "templates": {"science": "B.S. {field}, {institution} {year}"},
                    "institution_pool": "institutions/university",
                },
            },
            "professions": {
                "_default": {"fields": ["Liberal Arts"], "tiers": {"bachelors": 1}},
            },
            "science_fields_pool": "fields/science",
        },
    )
    assert education.tier_defaults["bachelors"].grad_age == 22
    assert education.tier_defaults["bachelors"].institution_pool == "institutions/university"
    assert education.professions["_default"].fields == ["Liberal Arts"]
    assert education.science_fields_pool == "fields/science"


def test_education_data_defaults_science_fields_pool():
    education = EducationData.from_dict({"tier_defaults": {}, "professions": {}})
    assert education.science_fields_pool == "fields/science"


def test_employer_data_from_dict():
    employer = EmployerData.from_dict(
        {
            "professions": {
                "federal agent": {"options": [{"pool": "employers/federal-law"}]},
                "police officer": {
                    "options": [{"weight": 3, "template": "{city} Police Department"}],
                },
                "_default": {"options": [{"literal": ""}]},
            },
        },
    )
    option = employer.professions["federal agent"].options[0]
    assert option.pool == "employers/federal-law"
    assert option.weight == 1  # default when omitted
    template_option = employer.professions["police officer"].options[0]
    assert template_option.weight == 3
    assert template_option.template == "{city} Police Department"


def test_damage_dice_and_die_type_come_as_a_pair():

    assert Damage.from_dict({"dice": 2, "die-type": 8}).die_type == 8
    assert Damage.from_dict({"special": "Victim -40%"}).dice is None  # no roll at all is fine
    for half in ({"dice": 2}, {"die-type": 8}):
        with pytest.raises(ValueError, match=r"dice.*die-type"):
            Damage.from_dict(half)


def test_every_model_annotation_resolves_at_runtime():
    """Annotations imported only under TYPE_CHECKING make `typing.get_type_hints` raise
    NameError, which breaks anything that introspects the models."""

    for obj in vars(models).values():
        if dataclasses.is_dataclass(obj):
            typing.get_type_hints(obj)  # raises NameError if an annotation can't be resolved


class TestTemplatesAreValidatedWhenLoaded:
    def test_education_tier_rejects_an_unknown_placeholder(self):
        with pytest.raises(TemplateError, match="degree"):
            EducationTier.from_dict(
                {
                    "grad_age": 22,
                    "templates": {"default": "{degree}, {institution} {year}"},
                    "institution_pool": "institutions/university",
                },
            )

    def test_education_tier_accepts_the_documented_placeholders(self):
        tier = EducationTier.from_dict(
            {
                "grad_age": 22,
                "templates": {
                    "science": "B.S. {field}, {institution} {year}",
                    "arts": "B.A. {field}",
                },
                "institution_pool": "institutions/university",
            },
        )
        assert tier.grad_age == 22

    def test_employer_option_rejects_an_unknown_placeholder(self):
        with pytest.raises(TemplateError, match="state"):
            EmployerOption.from_dict({"template": "{state} Highway Patrol"})

    def test_employer_option_rejects_format_string_tricks(self):
        with pytest.raises(TemplateError):
            EmployerOption.from_dict({"template": "{city.__class__}"})

    def test_employer_option_accepts_city(self):
        assert EmployerOption.from_dict({"template": "{city} Police"}).template == "{city} Police"


class TestProfessionRosterLabel:
    def test_joins_label_employer_and_division_skipping_blanks(self):
        base = {
            "label": "Federal Agent",
            "number_to_generate": 1,
            "skills": {"fixed": {}},
            "bonds": 0,
        }
        assert Profession.from_dict(base).roster_label() == "Federal Agent"
        with_employer = Profession.from_dict({**base, "employer": "FBI"})
        assert with_employer.roster_label() == "Federal Agent, FBI"
        full = Profession.from_dict({**base, "employer": "FBI", "division": "CID"})
        assert full.roster_label() == "Federal Agent, FBI, CID"
