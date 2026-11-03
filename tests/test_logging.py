"""Logging: diagnostics go to stderr, warnings show by default, nothing global is silenced."""

from __future__ import annotations

import json
import logging
import warnings

import pytest

from dggen import config
from dggen.cli import main
from dggen.logging_setup import init_logger

logger = logging.getLogger("dggen")


@pytest.fixture(autouse=True)
def _restore_logger():
    handlers, level, propagate = list(logger.handlers), logger.level, logger.propagate
    yield
    logger.handlers[:] = handlers
    logger.setLevel(level)
    logger.propagate = propagate


class TestLevels:
    @pytest.mark.parametrize(
        ("verbosity", "level"),
        [(0, logging.WARNING), (1, logging.INFO), (2, logging.DEBUG), (3, logging.DEBUG)],
    )
    def test_each_verbosity_sets_a_level(self, verbosity, level):
        init_logger(verbosity)
        assert logger.level == level

    def test_warnings_are_visible_without_any_flag(self, capsys):
        init_logger(0)
        logger.warning("something got truncated")
        logger.info("chatter")
        err = capsys.readouterr().err
        assert "something got truncated" in err
        assert "chatter" not in err

    def test_the_most_verbose_level_adds_timestamps_and_locations(self, capsys):
        init_logger(3)
        logger.debug("detail")
        assert "test_logging.py" in capsys.readouterr().err
        init_logger(2)
        logger.debug("detail")
        assert capsys.readouterr().err.strip() == "detail"


class TestStreams:
    def test_logs_go_to_stderr_and_stdout_stays_clean(self, capsys):
        init_logger(0)
        logger.error("boom")
        captured = capsys.readouterr()
        assert "boom" in captured.err
        assert captured.out == ""

    def test_the_stream_is_resolved_when_called_not_when_imported(self, capsys):
        """A default argument of `sys.stdout` is bound once, at import - before anything (pytest,
        a wrapper, a redirect) has replaced it."""
        init_logger(0)
        logger.warning("late")
        assert "late" in capsys.readouterr().err

    def test_calling_it_again_replaces_the_handler_instead_of_duplicating_output(self, capsys):
        init_logger(0)
        init_logger(0)
        logger.warning("once")
        assert capsys.readouterr().err.count("once") == 1


class TestNothingGlobalIsSilenced:
    def test_the_warnings_filters_are_left_alone(self):
        before = list(warnings.filters)
        init_logger(0)
        assert warnings.filters == before

    def test_other_librarys_warnings_are_still_reported(self):
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("default")
            init_logger(0)
            warnings.warn("from some dependency", UserWarning, stacklevel=1)
        assert [str(w.message) for w in caught] == ["from some dependency"]

    def test_only_the_dggen_logger_is_configured(self):
        root_handlers = list(logging.getLogger().handlers)
        init_logger(2)
        assert logging.getLogger().handlers == root_handlers


class TestFromTheCommandLine:
    def test_a_truncation_warning_is_visible_with_no_flags(self, tmp_path, capsys):
        """Gear dropped because it doesn't fit the sheet used to be reported only with -v."""
        equipment = json.loads(config.DEFAULT_EQUIPMENT.read_text("utf-8"))
        equipment["kits"]["agent"]["gear"] += [{"text": f"Extra item {i}"} for i in range(40)]
        path = tmp_path / "equipment.json"
        path.write_text(json.dumps(equipment), encoding="utf-8")
        assert main(["-t", "agent", "--seed", "1", "--equipment", str(path)]) == 0
        captured = capsys.readouterr()
        assert "dropped" in captured.err
        assert "Extra item" in captured.err
        assert "dropped" not in captured.out  # the character summary stays machine-readable

    def test_an_error_goes_to_stderr_too(self, capsys):
        assert main(["-t", "no such profession"]) == 2
        captured = capsys.readouterr()
        assert "Unknown profession" in captured.err
        assert captured.out == ""

    def test_the_ambiguous_profession_note_is_a_normal_warning(self, capsys):
        fbi = str(config.DATA_DIR / "professions-fbi.json")
        assert main(["-t", "Federal Agent", "--professions", fbi, "-c", "1", "--seed", "1"]) == 0
        assert "using cid" in capsys.readouterr().err
