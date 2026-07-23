"""Unit tests for dataclass from_dict parsing (hyphenated keys, defaults)."""

from __future__ import annotations

from dggen.models import Kit, Profession, ProfessionSkills, Weapon


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
    assert weapon.damage.dice == 1
    assert weapon.damage.die_type == 10
    assert weapon.damage.db_applies is True


def test_kit_defaults_gear_to_empty():
    kit = Kit.from_dict({"weapons": [], "armour": []})
    assert kit.gear == []
