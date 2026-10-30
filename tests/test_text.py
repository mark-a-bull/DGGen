"""Unit tests for the pure text/date helpers."""

from __future__ import annotations

import argparse
from datetime import date

import pytest

from dggen.text import (
    TemplateError,
    age_on,
    fill_template,
    format_details,
    format_name,
    parse_date,
    shrink_to_fit,
)


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

    @pytest.mark.parametrize(
        ("given", "expected"),
        [
            ("  John Smith  ", "SMITH, John"),
            ("John   Smith", "SMITH, John"),
            ("SMITH,John", "SMITH, John"),
            ("SMITH ,  John", "SMITH, John"),
            ("  SMITH, John  ", "SMITH, John"),
        ],
        ids=["outer-space", "inner-space", "no-space-after-comma", "loose-comma", "padded-comma"],
    )
    def test_stray_whitespace_is_normalised(self, given, expected):
        assert format_name(given) == expected

    @pytest.mark.parametrize(
        ("given", "expected"),
        [
            ("John Smith Jr.", "SMITH, John Jr."),
            ("Dr. John Smith Jr.", "SMITH, Dr. John Jr."),
            ("John Smith III", "SMITH, John III"),
            ("John Smith, Jr.", "SMITH, John Jr."),
            ("John Smith sr", "SMITH, John sr"),
        ],
    )
    def test_generational_suffix_stays_with_the_given_name(self, given, expected):
        """A suffix is not a surname: "John Smith Jr." must not become "JR., John Smith"."""
        assert format_name(given) == expected


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
            "abcdefghij",
            8,
            max_width=18,
            measure=self.measure,
            min_size=6,
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


class TestFillTemplate:
    """Templates come from data files (which `--employer-data`/`--education-data` let anyone
    swap), so substitution must not behave like `str.format` (attribute access, indexing, format
    specs) and a bad template must fail with a message, not a bare IndexError/KeyError."""

    def test_substitutes_plain_placeholders(self):
        assert fill_template("{city} Police Department", city="Salem") == "Salem Police Department"
        assert fill_template("{a}-{b}-{a}", a="x", b="y") == "x-y-x"

    def test_a_template_without_placeholders_is_returned_as_is(self):
        assert fill_template("U.S. Navy") == "U.S. Navy"

    def test_doubled_braces_are_literal_braces_as_in_str_format(self):
        assert fill_template("{{city}} is {city}", city="Salem") == "{city} is Salem"

    def test_substituted_values_are_not_reinterpreted(self):
        assert fill_template("{city}", city="{field}") == "{field}"

    def test_numbers_are_formatted_plainly(self):
        assert fill_template("Class of {year}", year=1999) == "Class of 1999"

    @pytest.mark.parametrize(
        "template",
        [
            "{city.__class__}",  # attribute access
            "{city.__init__.__globals__}",
            "{0}",  # positional index
            "{city[0]}",  # item access
            "{year:04d}",  # format spec
            "{city!r}",  # conversion
            "{}",  # empty field
            "oops {city",  # unbalanced
            "oops city}",
        ],
    )
    def test_anything_but_a_plain_name_is_rejected(self, template):
        with pytest.raises(TemplateError, match="brace"):
            fill_template(template, city="Salem", year=1999)

    def test_unknown_placeholder_names_what_is_available(self):
        with pytest.raises(TemplateError) as exc:
            fill_template("{town} PD", city="Salem")
        assert "town" in str(exc.value)
        assert "city" in str(exc.value)

    def test_template_error_is_a_value_error(self):
        assert issubclass(TemplateError, ValueError)
