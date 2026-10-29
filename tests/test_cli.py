"""CLI-level behaviour for bad input: a clear usage error or exit code, never a traceback."""

from __future__ import annotations

import pytest

from dggen.cli import main


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
