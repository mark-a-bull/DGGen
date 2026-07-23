"""Tests for auto-generated education/occupational history."""

from __future__ import annotations

from datetime import datetime

import pytest


class TestGenerateEducation:
    def test_default_generates_education(self, make_character):
        char = make_character(profession="Anthropologist")
        assert char.education

    def test_override_wins_and_skips_generation(self, make_character):
        char = make_character(profession="Anthropologist", education_override="Custom Bio")
        assert char.education == "Custom Bio"

    def test_disabled_leaves_field_blank(self, make_character):
        char = make_character(profession="Anthropologist", auto_education=False)
        assert char.education is None
        assert "education" not in char.d

    def test_unknown_profession_label_falls_back_to_default(self, make_character, data):
        # A profession not present in education.json's "professions" map should still get a
        # plausible bio via the "_default" entry, not crash.
        from dggen.character import Character
        from dggen.rng import Rng

        rng = Rng(3)
        prof = data.professions["agent"]
        # Force a label education.json has never heard of.
        prof.label = "Completely Unlisted Job Title"
        char = Character.generate(data=data, rng=rng, sex="male", profession=prof)
        assert char.education

    def test_too_young_for_any_tier_leaves_field_blank(self, make_character):
        # data/education.json's lowest grad_age across all tiers is 18 (highschool). An age below
        # that has no eligible tier for any profession.
        char = make_character(profession="Anthropologist", min_age=10, max_age=10)
        assert char.education is None


class TestDegreeFieldConsistency:
    """Regression coverage for the B.S./B.A. (and M.S./M.A.) mismatch bug: degree phrasing must
    match the field's science/arts classification, not be chosen independently at random."""

    @pytest.mark.parametrize(
        ("profession", "science_terms"),
        [
            ("Computer Scientist", ("Computer Science",)),
            ("Engineer", ("Engineering",)),
            ("Nurse", ("Nursing",)),
        ],
    )
    def test_science_fields_never_get_arts_degree(self, make_character, profession, science_terms):
        for seed in range(30):
            char = make_character(profession=profession, seed=seed, min_age=22, max_age=60)
            if char.education and any(term in char.education for term in science_terms):
                assert "B.A." not in char.education
                assert "M.A." not in char.education

    def test_arts_fields_never_get_science_degree(self, make_character):
        for seed in range(30):
            char = make_character(profession="Historian", seed=seed, min_age=22, max_age=60)
            if char.education and "History" in char.education:
                assert "B.S." not in char.education
                assert "M.S." not in char.education


class TestAgeConsistency:
    def test_no_doctorate_before_grad_age(self, make_character):
        for seed in range(50):
            char = make_character(
                profession="Anthropologist", seed=seed, min_age=25, max_age=27,
            )
            if char.education:
                assert "Ph.D." not in char.education

    def test_grad_year_not_in_the_future(self, make_character):
        current_year = datetime.now().year
        for seed in range(50):
            char = make_character(profession="Physician", seed=seed, min_age=26, max_age=70)
            if char.education:
                year = int(char.education.rstrip(".").rsplit(" ", 1)[-1])
                assert year <= current_year
