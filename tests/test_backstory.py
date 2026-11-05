"""Backstory: named bonds, motivations and personal details, and the page that carries them."""

from __future__ import annotations

import logging
from dataclasses import replace

import pytest
from pypdf import PdfReader
from reportlab.pdfbase import pdfmetrics

from dggen import appearance
from dggen.backstory import Backstory, BondDetail
from dggen.character import Character
from dggen.cli import build_parser, main
from dggen.data import load_data
from dggen.options import DataSources, GenerationOptions
from dggen.pdf import SheetWriter
from dggen.rng import Rng
from dggen.roster import generate_character
from dggen.rules import backstory as rule
from dggen.serialize import to_back_fields, to_front_fields
from dggen.sinks import PdfSink
from dggen.summary import BackstorySection, backstory_sections, describe_bond, format_details


def _make(data, profession="agent", seed=1, sex="male", **options):
    return generate_character(
        data, Rng(seed), sex, data.professions[profession], GenerationOptions(**options)
    )


class TestPools:
    @pytest.mark.parametrize("pool_id", rule.POOL_IDS)
    def test_every_pool_the_rule_draws_from_exists_and_has_enough_values(self, data, pool_id):
        values = data.pools.values(pool_id)
        assert len(values) >= 10  # a handful would make every character read alike
        assert len(values) == len(set(values))

    def test_there_are_enough_motivations_and_details_to_sample(self, data):
        assert len(data.pools.values(rule.MOTIVATIONS_POOL)) > rule.MOTIVATION_COUNT
        assert len(data.pools.values(rule.DETAILS_POOL)) > rule.DETAIL_COUNT


class TestGenerateBackstory:
    def test_every_surviving_bond_gets_a_named_person_with_its_own_score(self, data):
        char = _make(data, seed=3)
        assert char.bonds  # an agent has bonds, so the loop below is not vacuous
        assert char.backstory is not None
        assert [b.slot for b in char.backstory.bonds] == sorted(char.bonds)
        for bond in char.backstory.bonds:
            assert bond.score == char.bonds[bond.slot]
            assert bond.relationship
            assert bond.name.count(", ") == 1  # "SURNAME, Given", like the character's own name
            surname, given = bond.name.split(", ")
            assert surname == surname.upper()
            assert given

    def test_motivations_and_details_are_distinct_picks_from_their_pools(self, data):
        char = _make(data, seed=4)
        assert char.backstory is not None
        motivations = char.backstory.motivations
        details = char.backstory.personal_details
        assert len(motivations) == rule.MOTIVATION_COUNT == len(set(motivations))
        assert len(details) == rule.DETAIL_COUNT == len(set(details))
        assert set(motivations) <= set(data.pools.values(rule.MOTIVATIONS_POOL))
        assert set(details) <= set(data.pools.values(rule.DETAILS_POOL))

    def test_family_bonds_share_the_characters_surname_and_others_do_not(self, data):
        family = set(data.pools.values(rule.FAMILY_POOL))
        other = set(data.pools.values(rule.OTHER_POOL))
        seen_family = seen_other = 0
        for seed in range(40):
            char = _make(data, seed=seed, name_override="Ada Quill")
            assert char.name == "QUILL, Ada"
            assert char.backstory is not None
            for bond in char.backstory.bonds:
                surname = bond.name.split(",")[0]
                if bond.relationship in family:
                    assert surname == "QUILL"
                    seen_family += 1
                else:
                    assert bond.relationship in other
                    assert surname != "QUILL"  # someone else's own family name
                    seen_other += 1
        # Positive controls: both kinds really do come up, so the assertions above ran.
        assert seen_family > 10
        assert seen_other > 10

    def test_both_sexes_of_given_name_come_up(self, data):
        male = set(data.pools.values("names/male-given"))
        female = set(data.pools.values("names/female-given"))
        given = set()
        for seed in range(30):
            story = _make(data, seed=seed).backstory
            assert story is not None
            given |= {bond.name.split(", ")[1] for bond in story.bonds}
        assert given & (male - female)
        assert given & (female - male)

    def test_the_same_seed_gives_the_same_backstory(self, data):
        assert _make(data, seed=9).backstory == _make(data, seed=9).backstory
        assert _make(data, seed=9).backstory != _make(data, seed=10).backstory

    def test_a_damaged_veteran_only_gets_people_for_the_bonds_they_kept(self, data):
        """Veterancy can drop a bond; the backstory runs after it, so it names only survivors."""
        lost = 0
        for seed in range(60):
            char = _make(data, seed=seed, veterancy_enabled=True)
            assert char.backstory is not None
            lost += char.profession.bonds - len(char.bonds)
            assert [b.slot for b in char.backstory.bonds] == sorted(char.bonds)
        assert lost > 0  # positive control: some veteran really did lose one

    def test_no_backstory_option_leaves_it_out(self, data):
        assert _make(data, auto_backstory=False).backstory is None

    def test_character_generate_alone_does_not_make_a_backstory(self, data):
        char = Character.generate(
            data=data, rng=Rng(1), sex="male", profession=data.professions["agent"]
        )
        assert char.backstory is None


class TestSeedsAreUndisturbed:
    """The backstory is drawn after the equipment, so it must not move anything that came before
    it: people share seeds, and a new feature should not change the character a seed gives."""

    @pytest.mark.parametrize("profession", ["agent", "police", "soldier", "scientist"])
    def test_the_sheet_fields_are_the_same_with_or_without_it(self, data, profession):
        for seed in range(5):
            with_it = _make(data, profession, seed)
            without = _make(data, profession, seed, auto_backstory=False)
            assert to_front_fields(with_it) == to_front_fields(without)
            assert to_back_fields(with_it) == to_back_fields(without)
            assert with_it.backstory is not None


class TestAwkwardNames:
    """`--name` is free text, so the character's own surname may be missing or oddly shaped."""

    @pytest.mark.parametrize(
        ("name", "expected"),
        [("Smith Jr.", "SMITH"), ("VAN DYKE, Anna", "VAN DYKE"), ("Cher", "CHER")],
    )
    def test_family_bonds_take_the_surname_and_not_a_suffix(self, data, name, expected):
        family = set(data.pools.values(rule.FAMILY_POOL))
        surnames = set()
        for seed in range(60):
            story = _make(data, seed=seed, name_override=name).backstory
            assert story is not None
            surnames |= {
                bond.name.split(",")[0] for bond in story.bonds if bond.relationship in family
            }
        assert expected in surnames
        assert not [s for s in surnames if "Jr" in s]

    def test_a_character_with_no_surname_still_gets_family_with_a_surname(self, data):
        for seed in range(20):
            story = _make(data, seed=seed, name_override=", Kim").backstory
            assert story is not None
            for bond in story.bonds:
                assert bond.name.split(", ")[0].strip()

    def test_a_profession_with_no_bonds_still_gets_motivations_and_details(self, data):
        profession = replace(data.professions["agent"], bonds=0)
        char = generate_character(data, Rng(1), "male", profession, GenerationOptions())
        assert char.bonds == {}
        assert char.backstory is not None
        assert char.backstory.bonds == ()
        text = format_details(char)
        assert "Bonds:" not in text
        assert "Motivations:" in text


class TestNamePools:
    def test_bond_names_come_from_the_same_pools_as_the_characters_own(self, tmp_path):
        """--surnames, --male-given-names and --female-given-names apply to bonds too."""
        files = {}
        for key, value in (("sur", "ZZSUR"), ("male", "ZZMALE"), ("female", "ZZFEMALE")):
            files[key] = tmp_path / f"{key}.txt"
            files[key].write_text(value + "\n", encoding="utf-8")
        loaded = load_data(
            DataSources(
                surnames=str(files["sur"]),
                male_given_names=str(files["male"]),
                female_given_names=str(files["female"]),
            )
        )
        given, surnames = set(), set()
        for seed in range(30):
            story = generate_character(
                loaded, Rng(seed), "male", loaded.professions["agent"], GenerationOptions()
            ).backstory
            assert story is not None
            for bond in story.bonds:
                surname, given_name = bond.name.split(", ")
                surnames.add(surname)
                given.add(given_name)
        assert surnames == {"ZZSUR"}  # the character's own surname is ZZSUR too
        assert given == {"ZZMALE", "ZZFEMALE"}


class TestSummary:
    def test_names_the_bonds_and_lists_motivations_and_details(self, data):
        char = _make(data, seed=2)
        assert char.backstory is not None
        text = format_details(char)
        for bond in char.backstory.bonds:
            assert f"  {describe_bond(bond)}" in text
        assert "Motivations:" in text
        assert "Personal details:" in text
        assert "Bond 1:" not in text  # the named bonds replace the bare scores
        for line in (*char.backstory.motivations, *char.backstory.personal_details):
            assert f"  {line}" in text.splitlines()

    def test_without_a_backstory_the_bare_bond_scores_are_shown(self, data):
        text = format_details(_make(data, seed=2, auto_backstory=False))
        assert "Bond 1:" in text
        assert "Motivations:" not in text


class TestSections:
    def test_empty_parts_are_left_out(self):
        assert backstory_sections(Backstory()) == []
        only = backstory_sections(Backstory(motivations=("Keep a promise",)))
        assert only == [BackstorySection("Motivations", ("Keep a promise",))]

    def test_reading_order_is_bonds_motivations_details(self):
        story = Backstory(
            bonds=(BondDetail(0, "sibling", "ROE, Sam", 12),),
            motivations=("a",),
            personal_details=("b",),
        )
        assert [s.title for s in backstory_sections(story)] == [
            "Bonds",
            "Motivations",
            "Personal details",
        ]

    def test_a_bond_reads_relationship_person_in_reading_order_and_score(self):
        assert describe_bond(BondDetail(1, "mentor", "ROE, Sam", 9)) == "mentor: Sam ROE (9)"

    def test_a_bond_with_a_single_word_name_still_reads(self):
        assert describe_bond(BondDetail(0, "friend", "CHER", 7)) == "friend: CHER (7)"

    def test_is_empty_is_true_only_when_nothing_is_there(self):
        assert Backstory().is_empty()
        assert not Backstory(motivations=("a",)).is_empty()
        assert not Backstory(bonds=(BondDetail(0, "x", "A, B", 1),)).is_empty()
        assert not Backstory(personal_details=("a",)).is_empty()


class TestCli:
    def test_backstory_is_on_by_default_and_no_backstory_turns_it_off(self):
        parser = build_parser()
        assert parser.parse_args(["-t", "agent"]).auto_backstory is True
        assert parser.parse_args(["-t", "agent", "--no-backstory"]).auto_backstory is False

    def test_text_output_shows_it_and_the_flag_removes_it(self, capsys):
        assert main(["-t", "agent", "--seed", "1"]) == 0
        assert "Motivations:" in capsys.readouterr().out
        assert main(["-t", "agent", "--seed", "1", "--no-backstory"]) == 0
        assert "Motivations:" not in capsys.readouterr().out


def _pages(tmp_path, *extra):
    out = tmp_path / "bs.pdf"
    assert main(["-t", "nurse", "-c", "2", "--seed", "1", "--pdf", "-o", str(out), *extra]) == 0
    return PdfReader(str(out))


class TestPdf:
    def test_each_character_gets_a_third_page_carrying_their_backstory(self, tmp_path):
        reader = _pages(tmp_path)
        assert len(reader.pages) == 2 + 2 * 3  # covers, then front/back/backstory twice
        first = reader.pages[4].extract_text()
        assert first.startswith("BACKSTORY")
        assert "BONDS" in first
        assert "MOTIVATIONS" in first
        assert "PERSONAL DETAILS" in first
        assert reader.pages[7].extract_text().startswith("BACKSTORY")

    def test_no_backstory_means_no_third_page(self, tmp_path):
        assert len(_pages(tmp_path, "--no-backstory").pages) == 2 + 2 * 2

    def test_unequipped_sheets_have_no_backstory_page(self, tmp_path):
        reader = _pages(tmp_path, "-u")
        assert len(reader.pages) == 2 + 2 + 1  # covers, two single pages, blank back page
        assert not any(page.extract_text().startswith("BACKSTORY") for page in reader.pages)

    def test_a_sink_without_equipment_ignores_the_backstory_option(self, tmp_path):
        sink = PdfSink(
            tmp_path / "x.pdf", title=None, oconus=False, equip=False, count=None, backstory=True
        )
        assert sink.backstory is False
        assert sink.pages_per_sheet == 1

    def test_a_page_that_overflows_warns_and_stops(self, tmp_path, caplog):
        writer = SheetWriter(tmp_path / "long.pdf")
        sections = [BackstorySection("Bonds", tuple("x" * 40 for _ in range(80)))]
        with caplog.at_level(logging.WARNING, logger="dggen"):
            writer.add_backstory_page("ROE, Sam", sections)
        assert "does not fit" in caplog.text
        assert "Bonds: xxxx" in caplog.text  # says where it stopped
        assert "'ROE, Sam'" in caplog.text  # the name is quoted, so it cannot forge a log line

    def test_a_heading_is_never_left_alone_at_the_bottom(self, tmp_path, caplog, monkeypatch):
        """With room for the heading but not for a line under it, the heading is dropped too."""
        writer = SheetWriter(tmp_path / "orphan.pdf")
        recorder = _Recorder(writer.c)
        monkeypatch.setattr(writer, "c", recorder)
        sections = [
            BackstorySection("Bonds", tuple(f"line {i}" for i in range(37))),
            BackstorySection("Motivations", ("one",)),
        ]
        with caplog.at_level(logging.WARNING, logger="dggen"):
            writer.add_backstory_page("ROE, Sam", sections)
        texts = [text for _x, _y, text, _size in recorder.drawn]
        assert "BONDS" in texts
        assert "MOTIVATIONS" not in texts
        assert "Motivations" in caplog.text

    def test_a_word_too_wide_for_the_page_is_shrunk_not_run_off_the_edge(
        self, tmp_path, monkeypatch
    ):
        writer = SheetWriter(tmp_path / "wide.pdf")
        recorder = _Recorder(writer.c)
        monkeypatch.setattr(writer, "c", recorder)
        wide = "W" * 120
        sections = [BackstorySection("Personal details", (wide, f"short then {wide}"))]
        writer.add_backstory_page("N" * 90, sections)
        right_edge = appearance.PAGE_WIDTH - appearance.BACKSTORY_MARGIN
        checked = 0
        for x, _y, text, size in recorder.drawn:
            if text in ("BACKSTORY", "PERSONAL DETAILS"):
                continue  # the fixed headings are in another font and always short
            width = pdfmetrics.stringWidth(text, appearance.DEFAULT_FONT, size)
            assert x + width <= right_edge + 0.5
            checked += 1
        assert checked >= 3  # the name and both long lines were really drawn and measured
        assert any(size < appearance.BACKSTORY_BODY_SIZE for *_rest, size in recorder.drawn)


class _Recorder:
    """A canvas that remembers each string it was asked to draw, with its position and size."""

    def __init__(self, canvas):
        self._canvas = canvas
        self._size = 0
        self.drawn = []

    def setFont(self, name, size, *args):  # noqa: N802 - reportlab's name
        self._size = size
        return self._canvas.setFont(name, size, *args)

    def drawString(self, x, y, text, *args):  # noqa: N802 - reportlab's name
        self.drawn.append((x, y, text, self._size))
        return self._canvas.drawString(x, y, text, *args)

    def __getattr__(self, name):
        return getattr(self._canvas, name)


def test_options_default_to_a_backstory():
    assert GenerationOptions().auto_backstory is True
    assert replace(GenerationOptions(), auto_backstory=False).auto_backstory is False
