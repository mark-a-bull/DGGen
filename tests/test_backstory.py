"""Backstory: named bonds, motivations and personal details, and the page that carries them."""

from __future__ import annotations

import logging
from dataclasses import replace
from typing import ClassVar

import pytest
from pypdf import PdfReader
from reportlab.pdfbase import pdfmetrics

from dggen import appearance
from dggen.backstory import Backstory, BondDetail
from dggen.character import Character
from dggen.cli import build_parser, main
from dggen.data import load_data
from dggen.errors import DataError
from dggen.options import DataSources, GenerationOptions
from dggen.pdf import SheetWriter
from dggen.pools import Pools, UnknownPoolError
from dggen.rng import Rng
from dggen.roster import generate_character, generate_roster
from dggen.rules import backstory as rule
from dggen.serialize import to_back_fields, to_front_fields
from dggen.sinks import PdfSink
from dggen.summary import BackstorySection, backstory_sections, describe_bond, format_details
from dggen.validate import validate_backstory


def _make(data, profession="agent", seed=1, sex="male", **options):
    return generate_character(
        data, Rng(seed), sex, data.professions[profession], GenerationOptions(**options)
    )


def _relationships(data, pool_id):
    """The relationships in a bond pool, without any |male / |female tags."""
    return {rule.split_tag(value)[0] for value in data.pools.values(pool_id)}


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
        family = _relationships(data, rule.FAMILY_POOL)
        other = _relationships(data, rule.OTHER_POOL)
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
    """The backstory draws from a fork of the main stream, so it must not move anything: people
    share seeds, and a new feature should not change what a seed gives - for the first character
    of a roster *or any later one* (a shared stream would shift every character after the first)."""

    @pytest.mark.parametrize("profession", ["agent", "police", "soldier", "scientist"])
    def test_the_sheet_fields_are_the_same_with_or_without_it(self, data, profession):
        for seed in range(5):
            with_it = _make(data, profession, seed)
            without = _make(data, profession, seed, auto_backstory=False)
            assert to_front_fields(with_it) == to_front_fields(without)
            assert to_back_fields(with_it) == to_back_fields(without)
            assert with_it.backstory is not None

    @pytest.mark.parametrize("veterancy", [False, True], ids=["plain", "veterans"])
    def test_every_character_of_a_roster_is_the_same_with_or_without_it(self, data, veterancy):
        professions = [data.professions[k] for k in ("agent", "nurse", "soldier", "police")]

        def roster(**overrides):
            options = GenerationOptions(veterancy_enabled=veterancy, **overrides)
            return [
                (char.name, to_front_fields(char), to_back_fields(char), char.backstory)
                for _profession, char in generate_roster(
                    data, Rng(7), professions, options, count=4
                )
            ]

        with_it, without = roster(), roster(auto_backstory=False)
        assert len(with_it) == len(without) == 16
        for (name, front, back, story), (name_off, front_off, back_off, story_off) in zip(
            with_it, without, strict=True
        ):
            assert (name, front, back) == (name_off, front_off, back_off)
            assert story is not None
            assert story_off is None

    @pytest.mark.parametrize("seed", range(5))
    def test_the_main_stream_is_left_exactly_where_it_was(self, data, seed):
        """The direct form of the guarantee: after a character, the next draw is the same."""
        profession = data.professions["agent"]
        with_it, without = Rng(seed), Rng(seed)
        generate_character(data, with_it, "male", profession, GenerationOptions())
        generate_character(
            data, without, "male", profession, GenerationOptions(auto_backstory=False)
        )
        assert with_it.roll(1, 10**9) == without.roll(1, 10**9)

    def test_different_characters_still_get_different_backstories(self, data):
        """Positive control for the fork: it is seeded from the stream's state, so it must not
        collapse to one fixed backstory for everybody."""
        stories = {_make(data, seed=seed).backstory for seed in range(20)}
        assert len(stories) == 20


class TestSplitTag:
    @pytest.mark.parametrize(
        ("entry", "expected"),
        [
            ("father|male", ("father", "male")),
            ("mother|female", ("mother", "female")),
            ("cousin", ("cousin", None)),
            (" aunt | female ", ("aunt", "female")),
            ("odd|name|male", ("odd|name", "male")),
            ("sibling|other", ("sibling|other", None)),  # an unknown tag is left visible
        ],
    )
    def test_splits_a_trailing_sex_tag_off_a_relationship(self, entry, expected):
        assert rule.split_tag(entry) == expected

    def test_distinct_drops_repeats_and_keeps_order(self):
        assert rule.distinct(["b", "a", "b", "c", "a"]) == ["b", "a", "c"]


class TestSexMatchedNames:
    """A "father" gets a man's name and a "mother" a woman's; untagged relationships are either."""

    GENDERED: ClassVar[dict[str, str]] = {
        "father": "male",
        "stepfather": "male",
        "uncle": "male",
        "older brother": "male",
        "younger brother": "male",
        "mother": "female",
        "stepmother": "female",
        "aunt": "female",
        "older sister": "female",
        "younger sister": "female",
    }

    def test_every_gendered_relationship_in_the_bundled_pool_is_tagged(self, data):
        tags = dict(rule.split_tag(v) for v in data.pools.values(rule.FAMILY_POOL))
        for relationship, sex in self.GENDERED.items():
            assert tags[relationship] == sex, relationship

    def test_the_given_name_follows_the_tag(self, data):
        male = set(data.pools.values("names/male-given"))
        female = set(data.pools.values("names/female-given"))
        seen = {"male": 0, "female": 0}
        neutral = {"male": 0, "female": 0}
        for seed in range(250):
            story = _make(data, seed=seed).backstory
            assert story is not None
            for bond in story.bonds:
                given = bond.name.split(", ")[1]
                sex = self.GENDERED.get(bond.relationship)
                if sex == "male":
                    assert given in male, bond
                    seen["male"] += 1
                elif sex == "female":
                    assert given in female, bond
                    seen["female"] += 1
                elif given in male - female:
                    neutral["male"] += 1
                elif given in female - male:
                    neutral["female"] += 1
        # Positive controls: gendered bonds of both sexes came up, and untagged ones got both.
        assert seen["male"] > 20
        assert seen["female"] > 20
        assert neutral["male"] > 20
        assert neutral["female"] > 20

    def test_the_tag_never_shows_in_the_output(self, data):
        for seed in range(60):
            story = _make(data, seed=seed).backstory
            assert story is not None
            assert not [b for b in story.bonds if "|" in b.relationship]


class TestDuplicatePoolLines:
    def test_a_line_repeated_in_a_pool_is_never_drawn_twice(self, data, monkeypatch):
        real = Pools.values

        def values(self, ref):
            if ref == rule.MOTIVATIONS_POOL:
                return ["same"] * 5 + ["other"]
            return real(self, ref)

        monkeypatch.setattr(Pools, "values", values)
        for seed in range(40):
            story = _make(data, seed=seed).backstory
            assert story is not None
            assert sorted(story.motivations) == ["other", "same"]


class TestValidateBackstory:
    @staticmethod
    def _break(monkeypatch, replacements):
        """Make `Pools.values` return (or raise) something else for the given pool ids."""
        real = Pools.values

        def values(self, ref):
            if ref in replacements:
                outcome = replacements[ref]
                if isinstance(outcome, Exception):
                    raise outcome
                return outcome
            return real(self, ref)

        monkeypatch.setattr(Pools, "values", values)

    def test_the_bundled_pools_pass(self, data):
        validate_backstory(data)

    def test_a_missing_pool_is_named(self, data, monkeypatch):
        error = UnknownPoolError(rule.DETAILS_POOL, [])
        self._break(monkeypatch, {rule.DETAILS_POOL: error})
        with pytest.raises(DataError, match="backstory pool 'backstory/quirks'"):
            validate_backstory(data)

    @pytest.mark.parametrize("pool_id", [rule.MOTIVATIONS_POOL, rule.DETAILS_POOL])
    def test_a_pool_too_short_to_sample_is_reported(self, data, monkeypatch, pool_id):
        self._break(monkeypatch, {pool_id: ["only one"]})
        with pytest.raises(DataError, match="needs at least 2 different values"):
            validate_backstory(data)

    def test_repeats_do_not_count_towards_the_minimum(self, data, monkeypatch):
        self._break(monkeypatch, {rule.MOTIVATIONS_POOL: ["same", "same", "same"]})
        with pytest.raises(DataError, match="needs at least 2 different values"):
            validate_backstory(data)

    @pytest.mark.parametrize("line", ["father|mael", "|male", "a|b|c"])
    def test_a_malformed_tag_is_reported(self, data, monkeypatch, line):
        self._break(monkeypatch, {rule.FAMILY_POOL: ["cousin", line]})
        with pytest.raises(DataError, match="should be 'relationship'"):
            validate_backstory(data)

    def test_every_problem_is_reported_at_once(self, data, monkeypatch):
        self._break(
            monkeypatch,
            {rule.MOTIVATIONS_POOL: ["one"], rule.DETAILS_POOL: ["one"], rule.OTHER_POOL: ["x|y"]},
        )
        with pytest.raises(DataError, match=r"\(3 problems\)"):
            validate_backstory(data)

    def test_the_cli_exits_2_at_startup_and_prints_nothing(self, monkeypatch, capsys):
        self._break(monkeypatch, {rule.MOTIVATIONS_POOL: ["one"]})
        assert main(["-t", "agent", "--seed", "1"]) == 2
        captured = capsys.readouterr()
        assert captured.out == ""  # no half-printed roster
        assert "backstory/motivations" in captured.err

    def test_no_backstory_does_not_need_the_pools(self, monkeypatch, capsys):
        self._break(monkeypatch, {rule.MOTIVATIONS_POOL: ["one"]})
        assert main(["-t", "agent", "--seed", "1", "--no-backstory"]) == 0
        assert "Statistics:" in capsys.readouterr().out


class TestAwkwardNames:
    """`--name` is free text, so the character's own surname may be missing or oddly shaped."""

    @pytest.mark.parametrize(
        ("name", "expected"),
        [("Smith Jr.", "SMITH"), ("VAN DYKE, Anna", "VAN DYKE"), ("Cher", "CHER")],
    )
    def test_family_bonds_take_the_surname_and_not_a_suffix(self, data, name, expected):
        family = _relationships(data, rule.FAMILY_POOL)
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
        assert describe_bond(BondDetail(1, "mentor", "ROE, Sam", 9)) == "mentor: Sam ROE (bond 9)"

    def test_a_bond_with_a_single_word_name_still_reads(self):
        assert describe_bond(BondDetail(0, "friend", "CHER", 7)) == "friend: CHER (bond 7)"

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

    def test_the_backstory_page_carries_that_characters_own_backstory(self, tmp_path, data):
        """Each page holds its own character's name, bonds, motivations and details (whitespace
        is ignored, since the page wraps lines)."""
        reader = _pages(tmp_path)
        expected = list(
            generate_roster(data, Rng(1), [data.professions["nurse"]], GenerationOptions(), count=2)
        )
        assert len(expected) == 2
        pages = []
        for index, (_profession, char) in enumerate(expected):
            assert char.backstory is not None
            page = "".join(reader.pages[4 + 3 * index].extract_text().split())
            pages.append(page)
            assert "".join(char.name.split()) in page
            for section in backstory_sections(char.backstory):
                for line in section.lines:
                    assert "".join(line.split()) in page, line
        assert pages[0] != pages[1]  # different characters, different pages

    def test_a_sink_expecting_a_backstory_refuses_a_character_without_one(self, tmp_path, data):
        sink = PdfSink(tmp_path / "x.pdf", title=None, oconus=False, equip=True, count=None)
        char = _make(data, auto_backstory=False)
        with pytest.raises(ValueError, match="backstory"):
            sink.add(char)

    def test_a_sink_told_there_is_no_backstory_accepts_characters_without_one(self, tmp_path, data):
        out = tmp_path / "x.pdf"
        sink = PdfSink(out, title=None, oconus=False, equip=True, count=None, backstory=False)
        sink.begin([data.professions["agent"]])
        sink.start_profession(data.professions["agent"])
        sink.add(_make(data, auto_backstory=False))
        sink.finish()
        assert len(PdfReader(str(out)).pages) == 2 + 2  # covers, then front and back

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

    def test_an_overflowing_page_still_ends_cleanly_so_the_page_count_holds(self, tmp_path):
        writer = SheetWriter(tmp_path / "two.pdf", pages_per_sheet=2)
        too_long = [BackstorySection("Bonds", tuple(f"line {i}" for i in range(80)))]
        writer.add_backstory_page("ROE, Sam", too_long)
        writer.add_backstory_page("DOE, Jo", [BackstorySection("Bonds", ("fits",))])
        writer.c.save()
        assert len(PdfReader(str(tmp_path / "two.pdf")).pages) == 2

    def test_real_backstories_always_fit_their_page(self, tmp_path, data, caplog):
        """Negative control for the overflow warning: it must not fire on ordinary output."""
        writer = SheetWriter(tmp_path / "all.pdf", pages_per_sheet=3)
        longest = []
        with caplog.at_level(logging.WARNING, logger="dggen"):
            for profession in data.professions.values():
                for seed in range(3):
                    char = generate_character(
                        data,
                        Rng(seed),
                        "male",
                        profession,
                        GenerationOptions(veterancy_enabled=True),
                    )
                    assert char.backstory is not None
                    sections = backstory_sections(char.backstory)
                    longest.append(sum(len(s.lines) for s in sections))
                    writer.add_backstory_page(char.name, sections)
        assert "does not fit" not in caplog.text
        assert max(longest) >= 8  # the busiest were genuinely exercised (4 bonds + 2 + 2)

    def test_a_long_line_wraps_with_a_hanging_indent_inside_the_margins(
        self, tmp_path, monkeypatch
    ):
        writer = SheetWriter(tmp_path / "wrap.pdf")
        recorder = _Recorder(writer.c)
        monkeypatch.setattr(writer, "c", recorder)
        line = " ".join(["wandering"] * 30)
        writer.add_backstory_page("ROE, Sam", [BackstorySection("Personal details", (line,))])
        pieces = [d for d in recorder.drawn if d[2].startswith("wandering")]
        assert len(pieces) >= 3  # it really wrapped
        left = appearance.BACKSTORY_MARGIN
        right_edge = appearance.PAGE_WIDTH - left
        assert pieces[0][0] == left
        assert {x for x, *_ in pieces[1:]} == {left + appearance.BACKSTORY_HANGING_INDENT}
        for x, _y, text, size in pieces:
            assert size == appearance.BACKSTORY_BODY_SIZE  # wrapped, not shrunk
            assert x + pdfmetrics.stringWidth(text, appearance.DEFAULT_FONT, size) <= right_edge

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
