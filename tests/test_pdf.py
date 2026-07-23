"""Presentation-layer tests: field/coordinate consistency and a golden PDF smoke test."""

from __future__ import annotations

from dggen.cli import main
from dggen.pdf import SheetWriter


def test_every_emitted_field_has_a_coordinate(make_character, data):
    """Guard against silently-dropped sheet fields: every key a character emits into d/e must
    have an entry in field_xys (otherwise fill_field only logs and skips it)."""
    known = set(SheetWriter.field_xys)
    for profession in data.professions:
        char = make_character(
            profession=profession, seed=11, veterancy_enabled=True, damaged=True,
        )
        char.equip(char.profession.equipment_kit)
        char.print_footnotes()
        emitted = set(char.d) | set(char.e)
        assert emitted <= known, f"{profession}: missing coords for {sorted(emitted - known)}"


def test_cli_generates_valid_pdf(tmp_path):
    out = tmp_path / "roster.pdf"
    rc = main(
        [
            "-t", "Anthropologist",
            "-c", "1",
            "--name", "Dr. Arthur Finch",
            "--sex", "male",
            "--birthdate", "1986-11-24",
            "--seed", "42",
            "-o", str(out),
        ],
    )
    assert rc == 0
    assert out.exists()
    assert out.read_bytes().startswith(b"%PDF")


def test_cli_rejects_unknown_profession(tmp_path, caplog):
    rc = main(["-t", "Nonexistent Job", "-o", str(tmp_path / "x.pdf")])
    assert rc == 2


def test_cli_multiple_professions_builds_toc(tmp_path):
    """Exercises the >1 profession path, which renders a Table of Contents."""
    out = tmp_path / "roster.pdf"
    rc = main(["--seed", "1", "-o", str(out)])
    assert rc == 0
    assert out.read_bytes().startswith(b"%PDF")

