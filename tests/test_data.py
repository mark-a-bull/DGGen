"""Tests for profession lookup by key/label and its error behaviour."""

from __future__ import annotations

from dataclasses import replace

import pytest

from dggen.data import ProfessionNotFound, ambiguous_keys, find_profession, load_data


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


@pytest.fixture
def fbi_professions():
    from dggen import config
    from dggen.cli import get_options
    from dggen.rng import Rng

    options = get_options(["--pdf", "--professions", str(config.DATA_DIR / "professions-fbi.json")])
    return load_data(options, Rng(0)).professions


class TestAmbiguousLabels:
    def test_shared_label_reports_every_candidate_key(self, fbi_professions):
        assert ambiguous_keys(fbi_professions, "Federal Agent") == ["cid", "nsb-agent"]
        assert ambiguous_keys(fbi_professions, "federal agent") == ["cid", "nsb-agent"]

    def test_a_key_is_never_ambiguous_even_if_its_label_is_shared(self, fbi_professions):
        assert ambiguous_keys(fbi_professions, "cid") == []
        assert ambiguous_keys(fbi_professions, "CID") == []

    def test_unique_label_is_not_ambiguous(self, fbi_professions):
        unique = next(
            p.label
            for p in fbi_professions.values()
            if sum(q.label == p.label for q in fbi_professions.values()) == 1
        )
        assert ambiguous_keys(fbi_professions, unique) == []

    def test_a_key_beats_a_label_that_happens_to_match_it(self, fbi_professions):
        """Resolution must not depend on dict order: an exact key wins over any label."""
        first, second = list(fbi_professions)[:2]
        renamed = dict(fbi_professions)
        renamed[first] = replace(renamed[first], label=second)
        assert find_profession(renamed, second) is renamed[second]

    def test_cli_says_which_profession_it_picked(self, capsys):
        from dggen import config
        from dggen.cli import main

        fbi = str(config.DATA_DIR / "professions-fbi.json")
        assert main(["-t", "Federal Agent", "--professions", fbi, "-c", "1", "--seed", "1"]) == 0
        err = capsys.readouterr().err
        assert "cid" in err and "nsb-agent" in err and "using cid" in err

    def test_cli_is_quiet_when_the_key_is_exact(self, capsys):
        from dggen import config
        from dggen.cli import main

        fbi = str(config.DATA_DIR / "professions-fbi.json")
        assert main(["-t", "nsb-agent", "--professions", fbi, "-c", "1", "--seed", "1"]) == 0
        assert "using" not in capsys.readouterr().err
