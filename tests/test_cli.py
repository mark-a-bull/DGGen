"""CLI-level behaviour for bad input: a clear usage error or exit code, never a traceback."""

from __future__ import annotations

from datetime import date, timedelta

import pytest

from dggen.cli import build_parser, get_options, main, validate_options


@pytest.mark.parametrize(
    "argv",
    [
        ["-t", "agent", "-a", "40", "-A", "30"],
        ["-t", "agent", "-a", "-5"],
        ["-t", "agent", "-c", "0"],
        ["-t", "agent", "-c", "-1"],
        ["-t", "agent", "--pdf", "-o", "{tmp}/missing-dir/x.pdf"],
    ],
    ids=["min-above-max", "negative-age", "count-zero", "count-negative", "output-dir-missing"],
)
def test_invalid_options_are_a_usage_error(argv, tmp_path, capsys):
    argv = [arg.replace("{tmp}", str(tmp_path)) for arg in argv]
    with pytest.raises(SystemExit) as exc:
        main(argv)
    assert exc.value.code == 2
    assert "error:" in capsys.readouterr().err


@pytest.mark.parametrize(
    "argv",
    [
        ["-t", "agent", "--names", "xx_YY"],
        ["-t", "agent", "--professions", "no-such-file.json"],
        ["-t", "agent", "--equipment", "no-such-file.json"],
    ],
    ids=["bad-faker-locale", "missing-professions-file", "missing-equipment-file"],
)
def test_unusable_data_options_exit_2_instead_of_raising(argv):
    assert main(argv) == 2


@pytest.mark.parametrize(
    ("filename", "content"),
    [
        ("empty.txt", ""),
        ("bad-weight.csv", "town,pop\nA,lots\n"),
        ("allzero.csv", "town,pop\nA,0\n"),
    ],
)
def test_malformed_pool_file_exits_2_instead_of_raising(tmp_path, filename, content):
    path = tmp_path / filename
    path.write_text(content, encoding="utf-8")
    assert main(["-t", "agent", "--surnames", str(path)]) == 2


@pytest.mark.parametrize("which", ["next-year", "this-year", "tomorrow"])
def test_birth_date_must_be_in_the_past(which, capsys):

    today = date.today()
    flags = {
        "next-year": ["--birth-year", str(today.year + 1)],
        "this-year": ["--birth-year", str(today.year)],
        "tomorrow": ["--birthdate", (today + timedelta(days=1)).isoformat()],
    }[which]
    with pytest.raises(SystemExit) as exc:
        main(["-t", "agent", *flags])
    assert exc.value.code == 2
    assert "error:" in capsys.readouterr().err


@pytest.mark.parametrize(
    ("flag", "content"),
    [
        (
            "--employer-data",
            '{"professions": {"_default": {"options": [{"template": "{nope} Corp"}]}}}',
        ),
        (
            "--education-data",
            '{"tier_defaults": {"highschool": {"grad_age": 18, "institution_pool": '
            '"institutions/high-school", "templates": {"default": "{field.__class__}"}}}, '
            '"professions": {}}',
        ),
    ],
    ids=["employer-template", "education-template"],
)
def test_a_bad_template_in_a_data_file_exits_2_instead_of_raising(tmp_path, flag, content):
    path = tmp_path / "data.json"
    path.write_text(content, encoding="utf-8")
    assert main(["-t", "agent", flag, str(path)]) == 2


class TestParsingIsSeparateFromValidation:
    """The parser only describes the flags; the cross-flag rules live in `validate_options`."""

    def test_the_parser_alone_accepts_a_combination_the_rules_reject(self):
        options = build_parser().parse_args(["-a", "40", "-A", "30"])  # no -t, no --pdf, min > max
        assert (options.min_age, options.max_age, options.type, options.pdf) == (
            40,
            30,
            None,
            False,
        )

    def test_validate_options_enforces_the_rules(self, capsys):
        parser = build_parser()
        options = parser.parse_args(["-a", "40", "-A", "30", "--pdf"])
        with pytest.raises(SystemExit) as exc:
            validate_options(options, parser)
        assert exc.value.code == 2
        assert "min-age" in capsys.readouterr().err

    def test_validate_options_passes_a_valid_command_line(self):
        parser = build_parser()
        validate_options(parser.parse_args(["-t", "agent"]), parser)

    def test_get_options_still_does_both(self):
        with pytest.raises(SystemExit):
            get_options(["-a", "40", "-A", "30", "--pdf"])
        assert get_options(["-t", "agent"]).type == "agent"


def test_an_unparseable_birthdate_is_a_usage_error(capsys):
    with pytest.raises(SystemExit) as exc:
        main(["-t", "agent", "--birthdate", "not a date"])
    assert exc.value.code == 2
    assert "Invalid date" in capsys.readouterr().err
