"""Presentation-layer tests: field/coordinate consistency and a golden PDF smoke test."""

from __future__ import annotations

import re

import pytest

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
            "--pdf",
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
    rc = main(["--seed", "1", "--pdf", "-o", str(out)])
    assert rc == 0
    assert out.read_bytes().startswith(b"%PDF")



def _toc_rows(reader):
    """(text, y) for each dotted-leader row drawn on the TOC page (page 3, after the covers)."""
    rows = []

    def visit(text, cm, tm, font_dict, font_size):
        if ".." in text:
            rows.append((text.strip(), tm[5]))

    reader.pages[2].extract_text(visitor_text=visit)
    return rows


@pytest.mark.parametrize("extra", [["-u"], []], ids=["unequipped", "equipped"])
def test_toc_page_numbers_match_the_real_bookmarks(tmp_path, extra):
    """Every TOC row's printed page must be the page its bookmark really lands on - including
    when -c overrides the per-profession roster size, and for the blank back-page row."""
    from pypdf import PdfReader

    out = tmp_path / "roster.pdf"
    assert main(["--seed", "1", "-c", "2", "--pdf", "-o", str(out), *extra]) == 0
    reader = PdfReader(str(out))

    rows = _toc_rows(reader)
    bookmarks = [
        (entry.title, reader.get_destination_page_number(entry) + 1)
        for entry in reader.outline
        if entry.title != "Table of Contents"
    ]
    assert len(rows) == len(bookmarks)
    for (text, _y), (title, page) in zip(rows, bookmarks):
        printed = int(re.search(r"(\d+)$", text).group(1))
        assert printed == page, f"{title!r}: TOC says {printed}, bookmark is page {page}"


def test_toc_blank_back_page_row_is_on_the_page(tmp_path):
    from pypdf import PdfReader

    out = tmp_path / "roster.pdf"
    assert main(["--seed", "1", "-c", "1", "-u", "--pdf", "-o", str(out)]) == 0
    rows = _toc_rows(PdfReader(str(out)))
    blank = [(text, y) for text, y in rows if text.startswith("Blank Character Sheet")]
    assert len(blank) == 1
    assert 0 < blank[0][1] < 792  # US Letter height
    # ...and it sits directly below the last profession row, not somewhere arbitrary.
    assert blank[0][1] < min(y for text, y in rows if not text.startswith("Blank"))


def test_unencodable_stdout_does_not_abort_generation(tmp_path, monkeypatch):
    """The text summary is printed before the sheet is drawn. A legacy console codepage (e.g.
    cp1252 when output is redirected on Windows) can't encode non-Latin names (--names ru_RU), and
    that must degrade the console text, not kill the run before the PDF is written."""
    import io
    import sys

    stdout = io.TextIOWrapper(io.BytesIO(), encoding="cp1252", errors="strict")
    monkeypatch.setattr(sys, "stdout", stdout)
    out = tmp_path / "x.pdf"
    rc = main(
        ["-t", "agent", "-c", "1", "--name", "Дмитрий Иванов", "--seed", "1", "--pdf", "-o", str(out)],
    )
    assert rc == 0
    assert out.read_bytes().startswith(b"%PDF")
