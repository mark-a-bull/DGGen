"""Tests for the generation rules: pure helpers plus seeded invariants."""

from __future__ import annotations

import logging
from dataclasses import replace
from datetime import date
from itertools import pairwise
from typing import Any

import pytest

from dggen.character import Character
from dggen.constants import DEFAULT_SKILLS, FOOTNOTE_MARKERS, MONTHS, PHYSICAL_STATS, STATS
from dggen.models import KitGearEntry, WeaponRef
from dggen.rng import Rng
from dggen.rules.equipment import MAX_GEAR_LINES, MAX_WEAPONS
from dggen.rules.skills import generate_bonus_skills
from dggen.rules.stats import damage_bonus, generate_derived_attributes
from dggen.rules.veterancy import (
    captivity_or_imprisonment_changes,
    extreme_violence_changes,
    hard_experience_changes,
    skill_checks_at_age,
    stat_losses_at_age,
    things_man_was_not_meant_to_know_changes,
    veterancy_skill_boosts,
)
from dggen.serialize import to_back_fields as _to_back_fields
from dggen.serialize import to_front_fields as _to_front_fields
from dggen.text import age_on


def _front(char) -> dict[str, Any]:
    """The sheet's front fields; `Any` values so tests can compare them without narrowing."""
    return _to_front_fields(char)


def _back(char) -> dict[str, Any]:
    return _to_back_fields(char)


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
        assert all(earlier >= later for earlier, later in pairwise(values))


class TestDerivedAttributes:
    # (strength, constitution, power) -> (hit points, willpower, sanity, breaking point).
    # Expected values are written out, not recomputed with the production formula, so a change to
    # the formula fails here. STR + CON is even in every row: how a half-point of hit points
    # rounds is an open rules question (review item B9) that these deliberately don't pin down.
    @pytest.mark.parametrize(
        ("strength", "constitution", "power", "expected"),
        [
            (10, 12, 11, (11, 11, 55, 44)),
            (16, 16, 9, (16, 9, 45, 36)),
            (7, 9, 15, (8, 15, 75, 60)),
            (13, 15, 12, (14, 12, 60, 48)),
            (18, 18, 18, (18, 18, 90, 72)),
            (3, 3, 3, (3, 3, 15, 12)),
        ],
    )
    def test_formulas(self, make_character, strength, constitution, power, expected):
        char = make_character()
        char.stats.update(strength=strength, constitution=constitution, power=power)
        generate_derived_attributes(char)
        got = (char.hitpoints, char.willpower, char.sanity, char.breaking_point)
        assert got == expected
        assert char.current_sanity is None  # nothing lost yet

    def test_current_sanity_is_max_sanity_less_what_was_lost(self, make_character):
        char = make_character()
        char.stats.update(power=12)
        char.san_lost = 7
        generate_derived_attributes(char)
        assert char.sanity == 60
        assert char.current_sanity == 53
        assert char.breaking_point == 48  # still from maximum sanity, not current

    def test_all_six_stats_populated_and_in_range(self, make_character):
        char = make_character()
        assert set(char.stats) == set(STATS)
        for stat in STATS:
            assert 3 <= char.stats[stat] <= 18  # 3d6-style bounds for a rolled or pooled stat


class TestDeterminism:
    def test_same_seed_same_stats_and_skills(self, make_character):
        a = make_character(seed=7)
        b = make_character(seed=7)
        assert _front(a) == _front(b)

    def test_different_seed_differs(self, make_character):
        a = make_character(seed=7)
        b = make_character(seed=8)
        assert _front(a) != _front(b)


class TestOverrides:
    def test_overrides_applied_after_randomization(self, make_character):
        char = make_character(
            profession="Anthropologist",
            name_override="Dr. Arthur Finch",
            employer_override="Field Museum",
            education_override="PhD Harvard",
            birthdate=date(1986, 11, 24),
        )
        assert _front(char)["name"] == "FINCH, Dr. Arthur"
        assert _front(char)["employer"] == "Field Museum"
        assert _front(char)["education"] == "PhD Harvard"
        assert _front(char)["age"].startswith(str(char.age))
        # Random content still produced despite the overrides: anthropology is a fixed
        # professional skill (50) that bonus skills may raise further.
        assert _front(char)["anthropology"] >= 50
        assert all(stat in _front(char) for stat in STATS)


def _physical(char) -> int:
    return sum(char.stats[stat] for stat in PHYSICAL_STATS)


class TestVeterancy:
    """A veteran is the same character as a non-veteran of the same seed, plus experience.

    The two characters share every draw up to the veterancy step (stats, skills and bonus skills
    come before education, which is the first age-dependent draw), so they can be compared skill
    by skill. `today` is pinned so the ages are 30 and 56 whatever the date.
    """

    TODAY = date(2026, 1, 1)

    def _pair(self, make_character, profession="agent", seed=5, veteran_born=date(1970, 1, 1)):
        common = {"profession": profession, "seed": seed, "today": self.TODAY}
        base = make_character(birthdate=date(1996, 1, 1), **common)  # 30: below the 40+ losses
        vet = make_character(
            birthdate=veteran_born, veterancy_enabled=True, damaged=False, **common
        )
        # The premise of the comparison: same character up to the veterancy step.
        assert (base.stats["intelligence"], base.picked_skills, base.bonus_skills) == (
            vet.stats["intelligence"],
            vet.picked_skills,
            vet.bonus_skills,
        )
        return base, vet

    @pytest.mark.parametrize("profession", ["agent", "soldier", "nurse", "engineer"])
    def test_experience_only_ever_adds_to_skills(self, make_character, profession):
        base, vet = self._pair(make_character, profession)
        assert vet.age == 56
        assert set(vet.skills) == set(base.skills)
        assert all(vet.skills[name] >= base.skills[name] for name in base.skills)
        assert any(vet.skills[name] > base.skills[name] for name in base.skills)  # and it did

    @pytest.mark.parametrize("profession", ["agent", "soldier", "nurse", "engineer"])
    def test_only_professional_and_bonus_skills_gain_experience(self, make_character, profession):
        base, vet = self._pair(make_character, profession)
        eligible = {*base.profession.skills.fixed, *base.picked_skills, *base.bonus_skills}
        for name in base.skills:
            if name not in eligible:
                assert vet.skills[name] == base.skills[name], f"{name} gained without cause"

    def test_age_costs_physical_stats_and_nothing_else(self, make_character):
        base, vet = self._pair(make_character)  # age 56 loses 2 points in total
        assert _physical(base) - _physical(vet) == 2
        for stat in STATS:
            if stat not in PHYSICAL_STATS:
                assert vet.stats[stat] == base.stats[stat]

    def test_physical_stats_never_drop_below_one(self, make_character):
        # Age 96 is the maximum band: 32 points of loss, more than most characters have to give.
        base, vet = self._pair(make_character, veteran_born=date(1930, 1, 1))
        assert vet.age == 96
        assert all(vet.stats[stat] >= 1 for stat in PHYSICAL_STATS)
        available = sum(base.stats[stat] - 1 for stat in PHYSICAL_STATS)
        lost = sum(base.stats[stat] - vet.stats[stat] for stat in PHYSICAL_STATS)
        assert lost == min(32, available)  # takes everything it can, and no more


class TestEquipment:
    def test_unarmed_always_present_and_weapon_cap(self, make_character):
        char = make_character(profession="agent")
        char.equip("agent")
        assert _back(char)["weapon0"]  # slot 0 populated
        # At most 7 weapon slots (0-6).
        assert all(f"weapon{i}" not in _back(char) for i in range(7, 12))

    def test_overlong_gear_is_truncated_to_the_sheet_with_a_warning(self, make_character, caplog):

        char = make_character(profession="agent")
        kit = char.data.kits["agent"]
        kit.armour = []
        kit.gear = [KitGearEntry(text=f"Item {i}") for i in range(MAX_GEAR_LINES + 8)]
        with caplog.at_level(logging.WARNING, logger="dggen"):
            char.equip("agent")
        assert len(char.gear_lines) == MAX_GEAR_LINES
        assert char.gear_lines[-1] == f"Item {MAX_GEAR_LINES - 1}"
        assert not [
            key for key in _back(char) if key.startswith("gear") and int(key[4:]) >= MAX_GEAR_LINES
        ]
        assert "Item 29" in caplog.text  # the warning names what was dropped

    def test_overfull_weapon_list_warns_with_names_not_reprs(self, make_character, caplog):

        char = make_character(profession="agent")
        types = [t for t in char.data.weapons if t != "unarmed"][: MAX_WEAPONS + 2]
        char.data.kits["agent"].weapons = [WeaponRef(type=t) for t in types]
        with caplog.at_level(logging.WARNING, logger="dggen"):
            char.equip("agent")
        assert len(char.weapons) == MAX_WEAPONS
        dropped = [char.data.weapons[t].name for t in types[MAX_WEAPONS - 1 :]]
        assert all(name in caplog.text for name in dropped)
        assert "Weapon(" not in caplog.text  # no dataclass repr dumps


class TestBonusSkills:
    @pytest.mark.parametrize("seed", range(40))
    def test_bonus_skills_are_distinct_and_boosted_once(self, make_character, seed):
        """A profession-suggested bonus skill also appears in the shuffled ALL_BONUS tail; it
        must not be picked (and boosted +20) a second time."""

        char = make_character(profession="agent", seed=1)
        char.rng = Rng(seed)
        char.skills = dict(DEFAULT_SKILLS)
        char.bonus_skills = []
        # Every suggestion is picked (75% chance each) and each also sits in ALL_BONUS.
        char.profession.skills.bonus = ["accounting", "alertness", "athletics", "bureaucracy"]

        generate_bonus_skills(char)

        assert len(char.bonus_skills) == 8
        assert len(set(char.bonus_skills)) == 8
        for skill in char.bonus_skills:
            assert char.skills[skill] == DEFAULT_SKILLS.get(skill, 0) + 20


class TestVeterancySkillChecks:
    def _veteran_candidate(self, make_character, picked):

        char = make_character(profession="agent", seed=1)
        char.age = 60  # plenty of experience checks
        char.rng = Rng(5)
        # Optional skills that overlap the default skills (so they are non-zero either way).
        char.profession.skills.possible = {"ride": 50, "survival": 50, "swim": 50}
        char.picked_skills = list(picked)
        char.bonus_skills = []
        return char

    def test_unpicked_possible_skills_get_no_experience_checks(self, make_character):
        """Only skills the character actually has as professional skills earn experience; an
        optional skill that wasn't picked is just a default skill and must stay put."""

        char = self._veteran_candidate(make_character, picked=[])
        before = dict(char.skills)
        veterancy_skill_boosts(char)
        for skill in ("ride", "survival", "swim"):
            assert char.skills[skill] == before[skill], skill

    def test_picked_possible_skill_does_get_experience(self, make_character):

        char = self._veteran_candidate(make_character, picked=["ride"])
        before = dict(char.skills)
        veterancy_skill_boosts(char)
        assert char.skills["ride"] > before["ride"]
        assert char.skills["survival"] == before["survival"]

    def test_generate_records_the_picked_possible_skills(self, make_character):
        char = make_character(profession="agent", seed=3)
        possible = char.profession.skills.possible
        assert len(char.picked_skills) == char.profession.skills.possible_count
        assert set(char.picked_skills) <= set(possible)
        for skill in char.picked_skills:
            assert char.skills[skill] == possible[skill]


class TestBirthYear:
    @pytest.mark.parametrize("seed", range(40))
    def test_age_agrees_with_the_birthday_shown_on_the_sheet(self, make_character, seed):
        """With only a birth year given the month/day are random; the age must be the true age
        for that exact birthday, not just `this year - birth year`."""

        char = make_character(profession="agent", seed=seed, birth_year=1986)
        birthday = date(1986, MONTHS.index(char.birth_month_abbrev) + 1, char.birth_day)
        assert char.age == age_on(birthday, date.today())

    def test_both_sides_of_the_birthday_occur(self, make_character):
        """Guard against the test above passing vacuously: across seeds the age must take both
        of the two values a birth year allows."""
        ages = {make_character(profession="agent", seed=s, birth_year=1986).age for s in range(40)}
        assert len(ages) == 2


def _guaranteed_weapons(ref):
    """How many weapons this kit entry always contributes (a lower bound on what it yields)."""
    if ref.chance < 100:
        return 0
    if ref.type is not None:
        return 1
    if ref.one_of:
        return min(_guaranteed_weapons(option) for option in ref.one_of) or 1
    return sum(_guaranteed_weapons(part) for part in ref.both)


class TestKitsFitTheSheet:
    def test_every_bundled_kit_fits_the_weapon_slots(self, data):
        """A weapon the kit always grants but the sheet has no slot for is silently dropped, so
        it can never appear on any character - that is a data bug, not bad luck."""

        too_big = {}
        for name, kit in data.kits.items():
            guaranteed = 1 + sum(_guaranteed_weapons(ref) for ref in kit.weapons)  # +1: unarmed
            if guaranteed > MAX_WEAPONS:
                too_big[name] = guaranteed
        assert not too_big, f"kits that always overflow the {MAX_WEAPONS} weapon slots: {too_big}"

    def test_swat_kit_can_produce_either_grenade(self, make_character):
        """The stun and tear grenades are alternatives - each must be reachable."""
        seen = set()
        for seed in range(30):
            char = make_character(profession="agent", seed=seed)
            char.profession.equipment_kit = "swat"
            char.weapons = []
            char.equip("swat")
            seen |= {w.name for w in char.weapons if "renade" in w.name}
        assert len(seen) == 2, seen


class TestFootnotes:
    def test_same_note_keeps_its_marker_and_new_notes_get_new_ones(self, make_character):
        char = make_character(profession="agent", seed=1)
        first = char.store_footnote("one")
        assert char.store_footnote("one") == first
        assert char.store_footnote("two") != first

    def test_running_out_of_markers_warns_instead_of_crashing(self, make_character, caplog):
        """A custom kit with more distinct notes than there are markers used to die with a bare
        StopIteration from inside a defaultdict factory."""

        char = make_character(profession="agent", seed=1)
        with caplog.at_level(logging.WARNING, logger="dggen"):
            markers = [char.store_footnote(f"note {i}") for i in range(len(FOOTNOTE_MARKERS) + 3)]
        assert markers[: len(FOOTNOTE_MARKERS)] == list(FOOTNOTE_MARKERS)
        assert all(marker in FOOTNOTE_MARKERS for marker in markers)
        assert "footnote" in caplog.text.lower()


class TestCharacterConstruction:
    def test_a_character_always_has_a_profession(self, make_character):
        """`profession` used to start as None and be filled in later; every rule step then had to
        assume it was set. It is now a constructor argument."""

        char = make_character(profession="agent", seed=1)
        fresh = Character(char.data, char.rng, "female", char.profession)
        assert fresh.profession is char.profession


class TestSkillLabels:
    def test_skills_are_all_numeric_and_labels_live_apart(self, make_character):
        char = make_character(profession="engineer", seed=3)
        assert all(isinstance(score, int) for score in char.skills.values())
        assert char.skill_labels["craft1label"] == "Electrician"
        assert "craft1label" not in char.skills

    def test_the_sheet_still_receives_labels_and_scores(self, make_character):
        char = make_character(profession="engineer", seed=3)
        assert _front(char)["craft1label"] == "Electrician"
        assert _front(char)["craft1value"] == char.skills["craft1value"]


class TestStatLossesAtAge:
    @pytest.mark.parametrize(
        ("age", "expected"),
        [
            (25, 0), (39, 0), (40, 1), (49, 1), (50, 2), (59, 2), (60, 4), (69, 4),
            (70, 8), (79, 8), (80, 16), (89, 16), (90, 32), (120, 32),
        ],
    )  # fmt: skip
    def test_loses_physical_points_by_decade(self, age, expected):
        assert stat_losses_at_age(age) == expected


class TestDamagedVeteranLimits:
    """The effects stack (and POW/CHA/bonds drop by 3 each), so on an unlucky character they could
    take a value somewhere the game never goes. Floors: POW and CHA at 1, bonds at 1, current
    sanity at 0. Occult is deliberately NOT capped: the rules add +10/+20/+10 per effect and a
    damaged veteran may end well past 99%."""

    ALL_EFFECTS = (
        extreme_violence_changes,
        captivity_or_imprisonment_changes,
        hard_experience_changes,
        things_man_was_not_meant_to_know_changes,
    )

    def _fragile(self, make_character, *, power=3, charisma=3):
        char = make_character(profession="agent", seed=4)
        char.stats.update(power=power, charisma=charisma)
        char.bonds = dict.fromkeys(range(char.profession.bonds), charisma)
        return char

    @pytest.mark.parametrize(("start", "expected"), [(10, 7), (4, 1), (3, 1), (2, 1), (1, 1)])
    def test_extreme_violence_never_takes_charisma_below_one(self, make_character, start, expected):
        char = self._fragile(make_character, charisma=start)
        extreme_violence_changes(char, [])
        assert char.stats["charisma"] == expected

    @pytest.mark.parametrize(("start", "expected"), [(12, 9), (4, 1), (3, 1), (2, 1)])
    def test_captivity_never_takes_power_below_one(self, make_character, start, expected):
        char = self._fragile(make_character, power=start)
        captivity_or_imprisonment_changes(char, [])
        assert char.stats["power"] == expected

    def test_extreme_violence_takes_three_from_each_bond_but_never_to_zero(self, make_character):
        strong = self._fragile(make_character, charisma=12)
        extreme_violence_changes(strong, [])
        assert set(strong.bonds.values()) == {9}
        weak = self._fragile(make_character, charisma=3)
        extreme_violence_changes(weak, [])
        assert set(weak.bonds.values()) == {1}

    def test_a_profession_with_no_bonds_survives_hard_experience(self, make_character):
        char = make_character(profession="agent", seed=4)
        char.profession = replace(char.profession, bonds=0)
        char.bonds = {}
        hard_experience_changes(char, [])  # used to raise KeyError deleting a bond that isn't there
        assert char.bonds == {}

    def test_hard_experience_drops_the_last_bond(self, make_character):
        char = self._fragile(make_character, charisma=10)
        count = char.profession.bonds
        hard_experience_changes(char, [])
        assert set(char.bonds) == set(range(count - 1))

    def test_every_effect_on_the_most_fragile_character_stays_in_range(self, make_character):
        char = self._fragile(make_character, power=3, charisma=3)
        for effect in self.ALL_EFFECTS:
            effect(char, [])
        generate_derived_attributes(char)
        assert char.stats["power"] >= 1
        assert char.stats["charisma"] >= 1
        assert char.willpower >= 1
        assert all(bond >= 1 for bond in char.bonds.values())
        assert char.current_sanity is not None
        assert char.current_sanity >= 0

    def test_current_sanity_is_floored_at_zero(self, make_character):
        char = make_character()
        char.stats.update(power=4)  # maximum sanity 20
        char.san_lost = 31
        generate_derived_attributes(char)
        assert char.sanity == 20
        assert char.current_sanity == 0

    def test_current_sanity_still_counts_down_normally_above_zero(self, make_character):
        char = make_character()
        char.stats.update(power=12)
        char.san_lost = 25
        generate_derived_attributes(char)
        assert char.current_sanity == 35

    def test_occult_is_deliberately_uncapped(self, make_character):
        """A decision, not an oversight: the damaged-veteran bonuses stack past 99%."""
        char = self._fragile(make_character)
        char.skills["occult"] = 90
        for effect in (extreme_violence_changes, things_man_was_not_meant_to_know_changes):
            effect(char, [])
        assert char.skills["occult"] == 120  # 90 + 10 + 20
