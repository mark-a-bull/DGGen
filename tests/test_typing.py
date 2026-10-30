"""The package type-checks cleanly under `mypy --strict`, and so do the tests' own bodies."""

from __future__ import annotations

from pathlib import Path

from mypy import api

REPO = Path(__file__).resolve().parent.parent

# Fixtures and test functions are deliberately unannotated; their bodies are still checked.
_RELAXED = ["--allow-untyped-defs", "--allow-incomplete-defs", "--allow-untyped-calls"]


def _mypy(*args: str, tmp: Path) -> tuple[str, int]:
    out, _err, status = api.run(
        ["--config-file", str(REPO / "pyproject.toml"), "--cache-dir", str(tmp / "cache"), *args],
    )
    return out, status


def test_package_is_strictly_typed(tmp_path: Path) -> None:
    out, status = _mypy(str(REPO / "dggen"), tmp=tmp_path)
    assert status == 0, out


def test_tests_are_type_correct(tmp_path: Path) -> None:
    out, status = _mypy(str(REPO / "tests"), *_RELAXED, tmp=tmp_path)
    assert status == 0, out


def test_the_check_can_actually_fail(tmp_path: Path) -> None:
    """Guard against these tests passing vacuously (a wrong path, a config that checks nothing)."""
    bad = tmp_path / "bad.py"
    bad.write_text("def f(x: int) -> str:\n    return x\n", encoding="utf-8")
    out, status = _mypy(str(bad), tmp=tmp_path)
    assert status != 0
    assert "return-value" in out
