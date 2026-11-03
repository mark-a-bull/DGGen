"""The documented library API: what `import dggen` offers, and that it stays cheap to import."""

from __future__ import annotations

import importlib
import subprocess
import sys

import pytest

import dggen

PUBLIC = {
    "Character": "dggen.character",
    "Data": "dggen.models",
    "DataError": "dggen.errors",
    "DataSources": "dggen.options",
    "GenerationOptions": "dggen.options",
    "InvalidLocaleError": "dggen.data",
    "PoolError": "dggen.pools",
    "Profession": "dggen.models",
    "ProfessionNotFoundError": "dggen.data",
    "Rng": "dggen.rng",
    "TemplateError": "dggen.text",
    "find_profession": "dggen.data",
    "format_details": "dggen.summary",
    "generate_character": "dggen.roster",
    "generate_roster": "dggen.roster",
    "load_data": "dggen.data",
    "to_back_fields": "dggen.serialize",
    "to_front_fields": "dggen.serialize",
}


def test_the_public_surface_is_exactly_what_is_documented():
    """Adding to or removing from the public API should be a deliberate edit to this list."""
    assert set(dggen.__all__) == {*PUBLIC, "__version__"}
    assert len(dggen.__all__) == len(set(dggen.__all__))  # no duplicates


def test_the_lazy_loader_and_all_cannot_drift_apart():
    assert dggen._EXPORTS == PUBLIC


@pytest.mark.parametrize("name", sorted(PUBLIC))
def test_each_name_is_the_object_from_its_home_module(name):
    home = importlib.import_module(PUBLIC[name])
    assert getattr(dggen, name) is getattr(home, name)


def test_from_import_works_for_every_public_name():
    namespace: dict[str, object] = {}
    exec(f"from dggen import {', '.join(sorted(PUBLIC))}", namespace)
    assert set(PUBLIC) <= set(namespace)


def test_an_unknown_name_is_an_ordinary_attribute_error():
    with pytest.raises(AttributeError, match="no_such_thing"):
        dggen.no_such_thing  # noqa: B018


def test_dir_lists_the_public_names():
    assert set(PUBLIC) <= set(dir(dggen))


def test_importing_the_package_does_not_import_the_heavy_dependencies():
    """`import dggen` (e.g. to read __version__) must not pull in reportlab or Faker."""
    code = "import sys, dggen; print(sorted(m for m in ('reportlab', 'faker') if m in sys.modules))"
    result = subprocess.run(
        [sys.executable, "-c", code], capture_output=True, text=True, check=True
    )
    assert result.stdout.strip() == "[]"


def test_the_documented_example_works_with_only_top_level_names():
    data = dggen.load_data(dggen.DataSources())
    rng = dggen.Rng(7)
    options = dggen.GenerationOptions(name_override="Dr. Ada Quill")
    professions = [dggen.find_profession(data.professions, "Federal Agent")]
    [(profession, character)] = dggen.generate_roster(data, rng, professions, options, count=1)
    assert profession.label == "Federal Agent"
    assert character.name == "QUILL, Dr. Ada"
    assert "Statistics:" in dggen.format_details(character)
    assert "name" in dggen.to_front_fields(character)
    assert dggen.to_back_fields(character)  # equipped, so there is a back page


def test_the_documented_errors_can_be_caught_by_name():
    data = dggen.load_data(dggen.DataSources())
    with pytest.raises(dggen.ProfessionNotFoundError):
        dggen.find_profession(data.professions, "no such job")
