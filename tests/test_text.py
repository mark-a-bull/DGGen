"""Unit tests for the pure text/date helpers."""

from __future__ import annotations

import argparse
from datetime import date

import pytest

from dggen.text import age_on, format_details, format_name, parse_date, shrink_to_fit


class TestFormatName:
    def test_natural_order_is_reformatted(self):
        assert format_name("Dr. Arthur Finch") == "FINCH, Dr. Arthur"

    def test_simple_natural_order(self):
        assert format_name("Gabriel Remsey") == "REMSEY, Gabriel"

    def test_already_comma_formatted_is_untouched(self):
        assert format_name("SMITH, John") == "SMITH, John"

    def test_single_word_is_uppercased(self):
        assert format_name("Cher") == "CHER"

    def test_empty_string(self):
        assert format_name("") == ""


class TestParseDate:
    @pytest.mark.parametrize(
        "value",
        ["1986-11-24", "November 24, 1986", "Nov 24, 1986", "11/24/1986"],
    )
    def test_accepted_formats(self, value):
        assert parse_date(value) == date(1986, 11, 24)

    def test_invalid_raises_argparse_error(self):
        with pytest.raises(argparse.ArgumentTypeError):
            parse_date("not a date")


class TestAgeOn:
    def test_birthday_already_passed_this_year(self):
        assert age_on(date(1986, 1, 1), date(2026, 6, 1)) == 40

    def test_birthday_is_today(self):
        assert age_on(date(1986, 6, 1), date(2026, 6, 1)) == 40

    def test_birthday_not_yet_this_year(self):
        assert age_on(date(1986, 12, 31), date(2026, 6, 1)) == 39

    def test_birthday_tomorrow(self):
        assert age_on(date(1986, 6, 2), date(2026, 6, 1)) == 39


class TestShrinkToFit:
    # Synthetic width model: each character is `size` points wide.
    @staticmethod
    def measure(text, size):
        return len(text) * size

    def test_short_text_unchanged_and_same_size(self):
        text, size = shrink_to_fit("hi", 11, max_width=1000, measure=self.measure)
        assert (text, size) == ("hi", 11)

    def test_shrinks_font_before_truncating(self):
        # "abcdef" (6 chars) at size 11 = 66 > 60, must shrink to size 10 -> 60 <= 60.
        text, size = shrink_to_fit("abcdef", 11, max_width=60, measure=self.measure)
        assert text == "abcdef"
        assert size == 10

    def test_truncates_with_ellipsis_when_min_size_insufficient(self):
        text, size = shrink_to_fit(
            "abcdefghij", 8, max_width=18, measure=self.measure, min_size=6,
        )
        assert text.endswith("…")
        assert self.measure(text, size) <= 18


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
        for skill, score in char.skills.items():
            assert f"{score}%" in text

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
            profession="agent", seed=1, auto_employer=False, auto_education=False,
        )
        text = format_details(char)
        assert "Employer:" not in text
        assert "Education:" not in text
