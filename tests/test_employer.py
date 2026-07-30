"""Tests for auto-generated employer."""

from __future__ import annotations


class TestGenerateEmployer:
    def test_default_generates_employer(self, make_character):
        char = make_character(profession="Anthropologist")
        assert char.employer

    def test_override_wins_and_skips_generation(self, make_character):
        char = make_character(profession="Anthropologist", employer_override="Custom Corp")
        assert char.employer == "Custom Corp"

    def test_disabled_leaves_field_blank(self, make_character):
        char = make_character(profession="Anthropologist", auto_employer=False)
        assert char.employer == ""

    def test_profession_provided_employer_is_preserved(self, data):
        """Variant profession files (e.g. data/professions-fbi.json) intentionally hardcode a
        real employer/division; auto-generation must never overwrite that."""
        from dggen.character import Character
        from dggen.data import find_profession, load_data
        from dggen.cli import get_options
        from dggen.rng import Rng

        options = get_options(
            ["--seed", "0", "--professions", "data/professions-fbi.json", "--pdf"],
        )
        fbi_data = load_data(options, Rng(0))
        prof = find_profession(fbi_data.professions, "cid")
        char = Character.generate(data=fbi_data, rng=Rng(1), sex="male", profession=prof)
        assert char.employer == "FBI, CID"

    def test_unknown_profession_label_falls_back_to_default(self, make_character, data):
        from dggen.character import Character
        from dggen.rng import Rng

        rng = Rng(3)
        prof = data.professions["agent"]
        prof.label = "Completely Unlisted Job Title"
        char = Character.generate(data=data, rng=rng, sex="male", profession=prof)
        assert char.employer == ""  # _default has no employer


class TestTownAwareTemplates:
    def test_police_employer_sometimes_uses_hometown(self, make_character):
        # Police Officer weights the {city} Police Department template over the named
        # big-city pool, so across enough seeds at least one must use the character's own town.
        results = [make_character(profession="Police Officer", seed=s) for s in range(20)]
        assert all("Police Department" in c.employer for c in results)
        assert any(
            c.town.split(",")[0].strip() in c.employer for c in results
        ), "expected at least one {city} Police Department among 20 seeds"

    def test_firefighter_employer_always_fire_department(self, make_character):
        # Firefighter can resolve to either a {city} Fire Department or a named big-city pool;
        # either way it must not be blank.
        for seed in range(20):
            char = make_character(profession="Firefighter", seed=seed)
            assert "Fire" in char.employer
