"""Tests for profession lookup by key/label and its error behaviour."""

from __future__ import annotations

import pytest

from dggen.data import ProfessionNotFound, find_profession


def test_lookup_by_key(data):
    assert find_profession(data.professions, "agent").label == "Federal Agent"


def test_lookup_by_exact_label(data):
    assert find_profession(data.professions, "Federal Agent").label == "Federal Agent"


def test_lookup_is_case_insensitive(data):
    assert find_profession(data.professions, "federal agent").label == "Federal Agent"
    assert find_profession(data.professions, "AGENT").label == "Federal Agent"


def test_unknown_profession_raises_with_valid_options_listed(data):
    with pytest.raises(ProfessionNotFound) as exc:
        find_profession(data.professions, "Not A Real Job")
    message = str(exc.value)
    assert "Not A Real Job" in message
    assert "agent (Federal Agent)" in message
