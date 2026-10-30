"""The readable text summary of a character (what the CLI prints without --pdf)."""

from __future__ import annotations

from dggen.summary import format_details


class TestFormatDetails:
    def test_includes_identity_and_stats(self, make_character):
        char = make_character(profession="agent", seed=42, sex="female")
        text = format_details(char)
        assert char.name in text
        assert char.profession_label in text
        assert "Statistics:" in text
        strength = char.stats["strength"]
        assert f"  {'Strength':<14} {strength:3d}  (x5 {strength * 5})" in text

    def test_skills_section_lists_every_skill(self, make_character):
        char = make_character(profession="agent", seed=1)
        text = format_details(char)
        assert "Skills:" in text
        for score in char.skills.values():
            assert f"{score}%" in text

    def test_label_entries_are_folded_into_their_skill_not_listed_as_skills(self, make_character):
        """Profession data stores sub-skill names (craft1label: "Electrician") alongside the
        score (craft1value: 40) in `skills`; the text view must show one "Craft (Electrician)"
        line, not a bogus "Craft1Label ... Electrician%" skill."""
        char = make_character(profession="engineer", seed=3)
        assert char.skill_labels["craft1label"] == "Electrician"  # guard: fixture has labels
        text = format_details(char)
        assert "Label" not in text
        assert "Electrician%" not in text
        assert f"  {'Craft (Electrician)':<26} {char.skills['craft1value']}%" in text

    def test_bonds_section_present_when_bonds_exist(self, make_character):
        char = make_character(profession="agent", seed=1)
        assert char.bonds  # agent has 3 bonds
        text = format_details(char)
        assert "Bonds:" in text
        assert f"Bond 1: {char.bonds[0]}" in text

    def test_equipment_section_only_appears_once_equipped(self, make_character):
        char = make_character(profession="agent", seed=1)
        assert "Equipment:" not in format_details(char)

        char.equip(char.profession.equipment_kit)
        char.print_footnotes()
        text = format_details(char)
        assert "Equipment:" in text
        assert "Weapon:" in text

    def test_employer_and_education_lines_omitted_when_blank(self, make_character):
        char = make_character(
            profession="agent",
            seed=1,
            auto_employer=False,
            auto_education=False,
        )
        text = format_details(char)
        assert "Employer:" not in text
        assert "Education:" not in text
