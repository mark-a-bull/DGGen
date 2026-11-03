"""The readable text summary of a character (what the CLI prints without --pdf)."""

from __future__ import annotations

import re

from dggen.summary import format_details


def _skill_rows(text: str) -> list[tuple[str, int]]:
    """The (name, score) rows printed under "Skills:", in order."""
    block = text.split("\nSkills:\n", 1)[1].split("\n\n", 1)[0]
    rows = []
    for line in block.splitlines():
        match = re.fullmatch(r"  (.+?)\s+(\d+)%", line)
        assert match, f"not a skill row: {line!r}"
        rows.append((match.group(1), int(match.group(2))))
    return rows


class TestFormatDetails:
    def test_includes_identity_and_stats(self, make_character):
        char = make_character(profession="agent", seed=42, sex="female")
        text = format_details(char)
        assert char.name in text
        assert char.profession_label in text
        assert "Statistics:" in text
        strength = char.stats["strength"]
        assert f"  {'Strength':<14} {strength:3d}  (x5 {strength * 5})" in text

    def test_skills_section_lists_every_skill_once_with_its_own_score(self, make_character):
        """Row for row: a skill that is missing, repeated, or shown with another skill's score
        fails (a substring check on "{score}%" would pass any of those)."""
        char = make_character(profession="agent", seed=1)
        rows = _skill_rows(format_details(char))
        assert rows == [(name.title(), score) for name, score in sorted(char.skills.items())]
        assert len(rows) == len(char.skills) > 20  # the full default list plus the profession's

    def test_skills_are_sorted_by_name(self, make_character):
        names = [name for name, _ in _skill_rows(format_details(make_character(seed=2)))]
        assert names == sorted(names)

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
        rows = dict(_skill_rows(text))
        assert rows["Craft (Electrician)"] == char.skills["craft1value"]
        assert rows["Craft (Mechanic)"] == char.skills["craft2value"]
        assert not [name for name in rows if "label" in name.lower() or "value" in name.lower()]
        # one row per numeric skill: the labels add no rows of their own
        assert len(rows) == len(char.skills)

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
