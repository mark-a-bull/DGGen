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
            profession=profession,
            seed=11,
            veterancy_enabled=True,
            damaged=True,
        )
        char.equip(char.profession.equipment_kit)
        char.print_footnotes()
        emitted = set(char.d) | set(char.e)
        assert emitted <= known, f"{profession}: missing coords for {sorted(emitted - known)}"


def test_cli_generates_valid_pdf(tmp_path):
    out = tmp_path / "roster.pdf"
    rc = main(
        [
            "-t",
            "Anthropologist",
            "-c",
            "1",
            "--name",
            "Dr. Arthur Finch",
            "--sex",
            "male",
            "--birthdate",
            "1986-11-24",
            "--seed",
            "42",
            "--pdf",
            "-o",
            str(out),
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
    from pypdf.generic import Destination

    out = tmp_path / "roster.pdf"
    assert main(["--seed", "1", "-c", "2", "--pdf", "-o", str(out), *extra]) == 0
    reader = PdfReader(str(out))

    rows = _toc_rows(reader)
    bookmarks = []
    for entry in reader.outline:
        assert isinstance(entry, Destination)  # a flat outline: no nested lists
        page_index = reader.get_destination_page_number(entry)
        assert page_index is not None
        if entry.title != "Table of Contents":
            bookmarks.append((entry.title, page_index + 1))
    assert len(rows) == len(bookmarks)
    for (text, _y), (title, page) in zip(rows, bookmarks):
        trailing = re.search(r"(\d+)$", text)
        assert trailing, f"no page number at the end of {text!r}"
        printed = int(trailing.group(1))
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
        [
            "-t",
            "agent",
            "-c",
            "1",
            "--name",
            "Дмитрий Иванов",
            "--seed",
            "1",
            "--pdf",
            "-o",
            str(out),
        ],
    )
    assert rc == 0
    assert out.read_bytes().startswith(b"%PDF")


def test_every_weapon_name_fits_its_box_at_a_legible_size(tmp_path):
    """Weapon names are drawn in full and shrunk to fit the name column (not truncated)."""
    import json

    from dggen import config
    from dggen.text import shrink_to_fit

    writer = SheetWriter(tmp_path / "x.pdf")
    weapons = json.loads((config.DATA_DIR / "equipment.json").read_text("utf-8"))["weapons"]
    for slot in range(7):
        field = f"weapon{slot}"
        name_x = SheetWriter.field_xys[field][0]
        roll_x = SheetWriter.field_xys[f"{field}_roll"][0]
        max_width = SheetWriter.field_max_widths[field]
        assert name_x + max_width < roll_x, f"{field} would run into the next column"
        for weapon in weapons.values():
            text, size = shrink_to_fit(
                weapon["name"],
                SheetWriter.field_xys[field][2],
                max_width,
                writer._measure,
            )
            assert text == weapon["name"], f"{weapon['name']!r} had to be truncated"
            assert size >= 7, f"{weapon['name']!r} shrank to {size}pt"


def test_cover_colours_are_valid_pdf_colour_operands(tmp_path):
    """PDF colour components are 0-1. The cover used (255, 255, 255), which only looks white
    because viewers happen to clamp out-of-range values."""
    from pypdf import PdfReader

    out = tmp_path / "x.pdf"
    assert main(["-t", "agent", "-c", "1", "--seed", "1", "--pdf", "-o", str(out)]) == 0
    contents = PdfReader(str(out)).pages[0].get_contents()
    assert contents is not None
    cover = contents.get_data().decode("latin-1")
    components = [
        float(n)
        for line in cover.splitlines()
        if line.endswith((" rg", " RG"))
        for n in line.split()[:-1]
    ]
    assert components, "expected the cover to set a colour"
    assert all(0 <= c <= 1 for c in components), components


def test_long_name_profession_and_nationality_stay_inside_their_boxes(tmp_path):
    """--name, --label and -n take arbitrary text; it must shrink to fit its box on the sheet
    rather than run across the neighbouring box or off the page."""
    from pypdf import PdfReader
    from reportlab.pdfbase import pdfmetrics

    from dggen import config

    long = "Montgomery-Featherstonehaugh " * 4
    out = tmp_path / "x.pdf"
    rc = main(
        [
            "-t",
            "agent",
            "-c",
            "1",
            "--seed",
            "1",
            "--name",
            long,
            "--label",
            long,
            "-n",
            long,
            "--pdf",
            "-o",
            str(out),
        ],
    )
    assert rc == 0

    drawn = []

    def visit(text, cm, tm, font_dict, font_size):
        if text.strip():
            drawn.append((text, tm[4], tm[5], font_size))

    PdfReader(str(out)).pages[2].extract_text(visitor_text=visit)
    # (field start x, field start y) -> right edge of the box printed on the sheet
    boxes = {(75, 693): 340, (343, 693): 553, (343, 665): 553}
    found = {}
    for text, x, y, size in drawn:
        key = (round(x), round(y))
        if key in boxes:
            width = pdfmetrics.stringWidth(text, config.DEFAULT_FONT, size)
            found[key] = (x + width, boxes[key], size)
    assert set(found) == set(boxes), f"fields not found on the page: {set(boxes) - set(found)}"
    for key, (right, limit, size) in found.items():
        assert right <= limit, f"text at {key} ends at {right:.0f}, box ends at {limit}"
        assert size >= 6
