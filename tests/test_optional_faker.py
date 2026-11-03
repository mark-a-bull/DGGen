"""Faker is only needed for `--names`; nothing else should import it or fail without it."""

from __future__ import annotations

import subprocess
import sys

import pytest

from dggen.data import load_data
from dggen.errors import DataError
from dggen.options import DataSources


def _run(code: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, check=False)


def test_importing_the_cli_does_not_import_faker():
    result = _run("import sys, dggen.cli; print('faker' in sys.modules)")
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "False"


def test_generating_without_names_works_when_faker_is_not_installed():
    code = (
        "import sys; sys.modules['faker'] = None\n"  # makes `import faker` raise ImportError
        "from dggen import load_data, DataSources, Rng, generate_roster, GenerationOptions\n"
        "data = load_data(DataSources())\n"
        "agent = data.professions['agent']\n"
        "[(_, c)] = generate_roster(data, Rng(1), [agent], GenerationOptions(), count=1)\n"
        "print(c.name)\n"
    )
    result = _run(code)
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip()  # produced a name from the bundled pools


def test_names_without_faker_says_how_to_fix_it(monkeypatch):
    monkeypatch.setitem(sys.modules, "faker", None)
    with pytest.raises(DataError, match="faker"):
        load_data(DataSources(names_locale="en_US"))


def test_names_still_work_when_faker_is_installed():
    data = load_data(DataSources(names_locale="en_US"))
    assert data.family_names is not None
