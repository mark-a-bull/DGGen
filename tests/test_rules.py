"""Tests for the generation rules: pure helpers plus seeded invariants."""

from __future__ import annotations

from datetime import date

import pytest

from dggen.constants import PHYSICAL_STATS, STATS
from dggen.rules.stats import damage_bonus
from dggen.rules.veterancy import skill_checks_at_age


class TestDamageBonus:
    @pytest.mark.parametrize(
        ("strength", "expected"),
        [(1, -2), (4, -2), (5, -1), (8, -1), (12, 0), (16, 1), (17, 2)],
    )
    def test_step_function(self, strength, expected):
        assert damage_bonus(strength) == expected


class TestSkillChecksAtAge:
    def test_start_age_earns_full(self):
        assert skill_checks_at_age(25) == 4.0

    def test_decays_with_age(self):
        assert skill_checks_at_age(35) == pytest.approx(2.0)
        assert skill_checks_at_age(45) == pytest.approx(1.0)

    def test_monotonic_decrease(self):
        values = [skill_checks_at_age(a) for a in range(25, 80)]
        assert all(earlier >= later for earlier, later in zip(values, values[1:]))


class TestDerivedAttributes:
    def test_formulas(self, make_character):
        char = make_character()
        d = char.d
        assert d["hitpoints"] == round((d["strength"] + d["constitution"]) / 2.0)
        assert d["willpower"] == d["power"]
        assert d["sanity"] == d["power"] * 5
        assert d["breaking point"] == d["sanity"] - d["power"]

    def test_all_six_stats_populated_and_in_range(self, make_character):
        char = make_character()
        for stat in STATS:
            assert 1 <= char.d[stat] <= 18


class TestDeterminism:
    def test_same_seed_same_stats_and_skills(self, make_character):
        a = make_character(seed=7)
        b = make_character(seed=7)
        assert a.d == b.d

    def test_different_seed_differs(self, make_character):
        a = make_character(seed=7)
        b = make_character(seed=8)
        assert a.d != b.d


class TestOverrides:
    def test_overrides_applied_after_randomization(self, make_character):
        char = make_character(
            profession="Anthropologist",
            name_override="Dr. Arthur Finch",
            employer_override="Field Museum",
            education_override="PhD Harvard",
            birthdate=date(1986, 11, 24),
        )
        assert char.d["name"] == "FINCH, Dr. Arthur"
        assert char.d["employer"] == "Field Museum"
        assert char.d["education"] == "PhD Harvard"
        assert char.d["age"].startswith(str(char.age))
        # Random content still produced despite the overrides: anthropology is a fixed
        # professional skill (50) that bonus skills may raise further.
        assert char.d["anthropology"] >= 50
        assert all(stat in char.d for stat in STATS)


class TestVeterancy:
    def test_physical_stats_never_below_one(self, make_character):
        # An extreme age forces the maximum stat-loss band.
        char = make_character(
            seed=3, birthdate=date(1930, 1, 1), veterancy_enabled=True, damaged=False,
        )
        for stat in PHYSICAL_STATS:
            assert char.d[stat] >= 1

    def test_veterancy_boosts_are_nonnegative(self, make_character):
        base = make_character(seed=5, birthdate=date(1996, 1, 1))
        vet = make_character(
            seed=5, birthdate=date(1970, 1, 1), veterancy_enabled=True, damaged=False,
        )
        # A veteran's fixed professional skills should be at least their base value.
        for skill in base.profession.skills.fixed:
            if isinstance(base.d.get(skill), int):
                assert vet.d[skill] >= base.profession.skills.fixed[skill]


class TestEquipment:
    def test_unarmed_always_present_and_weapon_cap(self, make_character):
        char = make_character(profession="agent")
        char.equip("agent")
        assert char.e["weapon0"]  # slot 0 populated
        # At most 7 weapon slots (0-6).
        assert all(f"weapon{i}" not in char.e for i in range(7, 12))

    def test_gear_lines_capped(self, make_character):
        char = make_character(profession="soldier")
        char.equip("soldier")
        assert all(f"gear{i}" not in char.e for i in range(22, 40))
