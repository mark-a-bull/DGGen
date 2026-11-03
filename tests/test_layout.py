"""The sheet layout (where each field is drawn) is data, not code."""

from __future__ import annotations

import json

import pytest
from pypdf import PdfReader

from dggen import config
from dggen.constants import ALL_BONUS, DEFAULT_SKILLS, STATS
from dggen.errors import DataError
from dggen.layout import SheetLayout, load_layout
from dggen.pdf import SheetWriter
from dggen.validate import validate_data


def _write(tmp_path, content):
    path = tmp_path / "layout.json"
    path.write_text(json.dumps(content), encoding="utf-8")
    return path


MINIMAL = {
    "fields": {"Personal Data": {"name": [75, 693, 11]}},
    "max_widths": {"name": 260},
}


class TestTheBundledLayout:
    def test_loads_with_the_documented_shape(self):
        layout = load_layout()
        assert isinstance(layout, SheetLayout)
        assert layout.fields["name"] == (75, 693, 11)
        assert layout.fields["weapon0_roll"][0] > layout.fields["weapon0"][0]
        assert len(layout.fields) == 212  # every field the sheet has, flattened across groups
        assert layout.max_widths["name"] == 260

    def test_weapon_name_widths_follow_the_gap_before_the_roll_column(self):
        layout = load_layout()
        for slot in range(7):
            gap = layout.fields[f"weapon{slot}_roll"][0] - layout.fields[f"weapon{slot}"][0]
            assert layout.max_widths[f"weapon{slot}"] == gap - 4

    def test_every_stat_and_default_or_bonus_skill_has_a_coordinate(self):
        fields = load_layout().fields
        for stat in STATS:
            assert {stat, f"{stat}_x5", f"{stat}_distinguishing"} <= set(fields)
        assert set(DEFAULT_SKILLS) <= set(fields)
        assert set(ALL_BONUS) <= set(fields)

    def test_the_file_is_listed_in_config_and_exists(self):
        assert config.DEFAULT_SHEET_LAYOUT.is_file()


class TestLoadingFromAFile:
    def test_groups_are_flattened_and_order_is_kept(self, tmp_path):
        path = _write(
            tmp_path,
            {
                "fields": {"A": {"one": [1, 2, 3], "two": [4, 5, 6]}, "B": {"three": [7, 8, 9]}},
                "max_widths": {},
            },
        )
        assert list(load_layout(path).fields.items()) == [
            ("one", (1, 2, 3)),
            ("two", (4, 5, 6)),
            ("three", (7, 8, 9)),
        ]

    @pytest.mark.parametrize(
        ("content", "fragment"),
        [
            ({"max_widths": {}}, "fields"),
            ({"fields": {"A": {"x": [1, 2]}}, "max_widths": {}}, "x"),
            ({"fields": {"A": {"x": [1, 2, "big"]}}, "max_widths": {}}, "x"),
            ({"fields": {"A": {"x": [1, 2, 3]}, "B": {"x": [4, 5, 6]}}, "max_widths": {}}, "twice"),
            ({"fields": {"A": {"x": [1, 2, 3]}}, "max_widths": {"y": 10}}, "y"),
        ],
        ids=["no-fields", "short-entry", "non-number", "duplicate-field", "width-for-no-field"],
    )
    def test_a_bad_layout_raises_data_error_naming_the_problem(self, tmp_path, content, fragment):
        path = _write(tmp_path, content)
        with pytest.raises(DataError) as exc:
            load_layout(path)
        assert "layout.json" in str(exc.value)
        assert fragment in str(exc.value)

    def test_invalid_json_names_the_file(self, tmp_path):
        path = tmp_path / "layout.json"
        path.write_text("{not json", encoding="utf-8")
        with pytest.raises(DataError, match=r"layout.json"):
            load_layout(path)

    def test_a_weapon_slot_without_a_roll_column_is_rejected(self, tmp_path):
        content = {
            "fields": {"A": {"weapon0": [85, 480, 11]}},
            "max_widths": {},
            "weapon_slots": 1,
        }
        with pytest.raises(DataError, match="weapon0_roll"):
            load_layout(_write(tmp_path, content))


class TestTheWriterUsesWhicheverLayoutItIsGiven:
    def test_a_custom_layout_moves_the_text(self, tmp_path):
        custom = load_layout(
            _write(
                tmp_path,
                {"fields": {"Only": {"name": [10, 700, 9]}}, "max_widths": {"name": 260}},
            )
        )
        out = tmp_path / "x.pdf"
        writer = SheetWriter(out, layout=custom)
        writer.fill_field("name", "Smith")
        writer.c.showPage()
        writer.c.save()
        seen = []

        def visit(text, _cm, tm, _font_dict, font_size):
            if text.strip():
                seen.append((text.strip(), tm[4], tm[5], font_size))

        PdfReader(str(out)).pages[0].extract_text(visitor_text=visit)
        assert seen == [("Smith", 10, 700, 9)]

    def test_the_default_layout_is_what_the_writer_uses_without_one(self, tmp_path):
        assert SheetWriter(tmp_path / "x.pdf").layout.fields == load_layout().fields


class TestProfessionSkillsMustHaveASheetField:
    def test_unknown_skill_is_reported_with_its_profession(self, data):
        data.professions["agent"].skills.fixed["telepathy"] = 50
        with pytest.raises(DataError, match=r"agent.*telepathy"):
            validate_data(data)

    def test_unknown_possible_and_bonus_skills_too(self, data):
        data.professions["agent"].skills.possible["levitation"] = 40
        data.professions["agent"].skills.bonus.append("pyrokinesis")
        with pytest.raises(DataError) as exc:
            validate_data(data)
        assert "levitation" in str(exc.value)
        assert "pyrokinesis" in str(exc.value)

    def test_a_supplied_layout_is_the_one_checked(self, data, tmp_path):
        sparse = load_layout(_write(tmp_path, MINIMAL))
        with pytest.raises(DataError, match="accounting"):
            validate_data(data, sparse)
