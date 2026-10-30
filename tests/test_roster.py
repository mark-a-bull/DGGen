"""The library-level pipeline: generate a roster, then hand each character to output sinks."""

from __future__ import annotations

from dataclasses import replace

from pypdf import PdfReader
from pypdf.generic import Destination

from dggen.data import load_data
from dggen.options import DataSources, GenerationOptions
from dggen.rng import Rng
from dggen.roster import generate_roster
from dggen.sinks import PdfSink, TextSink


def _professions(data, *keys, number=2):
    return [replace(data.professions[key], number_to_generate=number) for key in keys]


class TestGenerateRoster:
    def test_yields_each_professions_own_roster_size_by_default(self, data):
        professions = _professions(data, "agent", "police", number=3)
        pairs = list(generate_roster(data, Rng(1), professions, GenerationOptions()))
        assert [p.label for p, _ in pairs] == [professions[0].label] * 3 + [
            professions[1].label
        ] * 3

    def test_count_overrides_the_roster_size(self, data):
        professions = _professions(data, "agent", "police", number=9)
        pairs = list(generate_roster(data, Rng(1), professions, GenerationOptions(), count=2))
        assert len(pairs) == 4

    def test_sex_alternates_per_profession_unless_fixed(self, data):
        professions = _professions(data, "agent", "police", number=3)
        alternating = generate_roster(data, Rng(1), professions, GenerationOptions())
        assert [c.sex for _, c in alternating] == ["female", "male", "female"] * 2
        fixed = generate_roster(data, Rng(1), professions, GenerationOptions(), sex="male")
        assert {c.sex for _, c in fixed} == {"male"}

    def test_characters_come_back_equipped_with_their_footnotes_flushed(self, data):
        [(_, char)] = list(
            generate_roster(
                data, Rng(1), _professions(data, "agent", number=1), GenerationOptions()
            )
        )
        assert len(char.weapons) > 1  # unarmed plus the kit
        assert char.gear_lines
        assert char.note_lines  # print_footnotes already ran

    def test_equip_can_be_turned_off(self, data):
        [(_, char)] = list(
            generate_roster(
                data,
                Rng(1),
                _professions(data, "agent", number=1),
                GenerationOptions(),
                equip=False,
            )
        )
        assert char.weapons == [] and char.gear_lines == []

    def test_is_reproducible_under_a_seed(self):
        """The same seed gives the same roster. The name providers must share the generation Rng
        (as the CLI wires them), so data is loaded per seed here rather than using a fixture."""

        def names(seed):
            rng = Rng(seed)
            data = load_data(DataSources(), rng)
            professions = _professions(data, "agent", number=3)
            return [c.name for _, c in generate_roster(data, rng, professions, GenerationOptions())]

        assert names(7) == names(7)
        assert names(7) != names(8)


class TestSinks:
    def test_text_sink_prints_each_character_followed_by_a_blank_line(self, data, capsys):
        sink = TextSink()
        professions = _professions(data, "agent", number=2)
        sink.begin(professions)
        for profession, char in generate_roster(data, Rng(1), professions, GenerationOptions()):
            sink.start_profession(profession)
            sink.add(char)
        sink.finish()
        out = capsys.readouterr().out
        assert out.count("Statistics:") == 2
        assert out.endswith("\n\n")

    def test_pdf_sink_writes_a_pdf_with_a_toc_when_there_are_several_professions(
        self, data, tmp_path
    ):
        out = tmp_path / "roster.pdf"
        professions = _professions(data, "agent", "police", number=1)
        sink = PdfSink(out, title="Test", oconus=False, equip=True, count=None)
        sink.begin(professions)
        current = None
        for profession, char in generate_roster(data, Rng(1), professions, GenerationOptions()):
            if profession is not current:
                sink.start_profession(profession)
                current = profession
            sink.add(char)
        sink.finish()
        reader = PdfReader(str(out))
        first = reader.outline[0]
        assert isinstance(first, Destination)
        assert first.title == "Table of Contents"
        assert len(reader.pages) == 2 + 1 + 2 * 2  # covers, TOC, then 2 pages per character
