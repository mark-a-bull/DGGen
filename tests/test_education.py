"""Tests for auto-generated education/occupational history."""

from __future__ import annotations

from datetime import date

import pytest

from dggen.character import Character
from dggen.rng import Rng
from dggen.serialize import to_front_fields


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
        assert "education" not in to_front_fields(char)

    def test_unknown_profession_label_falls_back_to_default(self, data):
        # A profession not present in education.json's "professions" map should still get a
        # plausible bio via the "_default" entry, not crash.

        rng = Rng(3)
        prof = data.professions["agent"]
        # Force a label education.json has never heard of.
        prof.label = "Completely Unlisted Job Title"
        char = Character.generate(data=data, rng=rng, sex="male", profession=prof)
        assert char.education

    def test_too_young_for_any_tier_leaves_field_blank(self, make_character):
        # dggen/data/education.json's lowest grad_age across all tiers is 18 (highschool). An age
        # below that has no eligible tier for any profession.
        char = make_character(profession="Anthropologist", min_age=10, max_age=10)
        assert char.education is None


TODAY = date(2026, 6, 1)  # pinned: graduation years are "this year minus years since graduating"


def _matching(make_character, profession, term, seeds=30):
    """Education strings (over many seeds) that mention `term`."""
    found = []
    for seed in range(seeds):
        char = make_character(profession=profession, seed=seed, min_age=22, max_age=60, today=TODAY)
        if char.education and term in char.education:
            found.append(char.education)
    return found


class TestDegreeFieldConsistency:
    """Regression coverage for the B.S./B.A. (and M.S./M.A.) mismatch bug: degree phrasing must
    match the field's science/arts classification, not be chosen independently at random.

    Each test first asserts that enough characters really do have the field in question, so the
    checks below can't silently pass because the data changed and nothing matches any more."""

    @pytest.mark.parametrize(
        ("profession", "term"),
        [
            ("Computer Scientist", "Computer Science"),
            ("Engineer", "Engineering"),
            ("Nurse", "Nursing"),
        ],
    )
    def test_science_fields_get_science_degrees_never_arts_ones(
        self, make_character, profession, term
    ):
        matched = _matching(make_character, profession, term)
        assert len(matched) >= 10, f"only {len(matched)} of 30 characters studied {term}"
        for education in matched:
            assert "B.A." not in education
            assert "M.A." not in education
        # ...and the science degrees really are what they get (not merely "not arts")
        assert any(("B.S." in e or "M.S." in e) for e in matched)

    def test_arts_fields_get_arts_degrees_never_science_ones(self, make_character):
        matched = _matching(make_character, "Historian", "History")
        assert len(matched) >= 10, f"only {len(matched)} of 30 characters studied History"
        for education in matched:
            assert "B.S." not in education
            assert "M.S." not in education
        assert any(("B.A." in e or "M.A." in e) for e in matched)


class TestAgeConsistency:
    def _anthropologists(self, make_character, low, high, seeds=50):
        return [
            make_character(
                profession="Anthropologist", seed=seed, min_age=low, max_age=high, today=TODAY
            )
            for seed in range(seeds)
        ]

    def test_no_doctorate_before_the_age_one_is_finished(self, make_character):
        young = self._anthropologists(make_character, 25, 27)
        assert all(c.education for c in young)  # they do have a history, so the check below bites
        assert not [c.education for c in young if "Ph.D." in c.education]

    def test_but_doctorates_do_occur_for_older_characters(self, make_character):
        """The positive control for the test above: without it a data change that stopped
        generating doctorates altogether would make that test pass for the wrong reason."""
        older = self._anthropologists(make_character, 45, 60)
        assert sum("Ph.D." in c.education for c in older if c.education) >= 10

    def test_graduation_year_is_the_years_since_graduating_counted_back_from_today(
        self, make_character, data
    ):
        grad_ages = {tier.grad_age for tier in data.education.tier_defaults.values()}
        checked = 0
        for seed in range(50):
            char = make_character(
                profession="Physician", seed=seed, min_age=26, max_age=70, today=TODAY
            )
            if not char.education:
                continue
            year = int(char.education.rstrip(".").rsplit(" ", 1)[-1])
            assert year <= TODAY.year
            assert (
                char.age - (TODAY.year - year) in grad_ages
            )  # i.e. year = today - (age - grad_age)
            checked += 1
        assert checked >= 40
