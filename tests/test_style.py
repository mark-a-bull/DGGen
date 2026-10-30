"""Lint and formatting stay clean (ruff config lives in pyproject.toml)."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
TARGETS = ["dggen", "tests", "generator.py"]


def _ruff(*args: str, cwd: Path = REPO) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "ruff", *args, "--no-cache"],
        cwd=cwd,
        capture_output=True,
        text=True,
        check=False,
    )


def test_lint_is_clean():
    result = _ruff("check", *TARGETS)
    assert result.returncode == 0, result.stdout + result.stderr


def test_formatting_is_clean():
    """Run `ruff format dggen tests generator.py` to fix."""
    result = _ruff("format", "--check", *TARGETS)
    assert result.returncode == 0, result.stdout + result.stderr


def test_the_checks_can_actually_fail(tmp_path):
    """Guard against passing vacuously (ruff missing a config, or checking nothing)."""
    (tmp_path / "pyproject.toml").write_text(
        (REPO / "pyproject.toml").read_text(encoding="utf-8"), encoding="utf-8"
    )
    bad = tmp_path / "bad.py"
    bad.write_text("import os\nx = {'a':1}\n", encoding="utf-8")  # unused import, ugly format
    assert _ruff("check", "bad.py", cwd=tmp_path).returncode != 0
    assert _ruff("format", "--check", "bad.py", cwd=tmp_path).returncode != 0
