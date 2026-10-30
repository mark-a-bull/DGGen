"""A built wheel must carry the data files the package reads at runtime.

`dggen.config` resolves every asset relative to the package, so anything missing from the wheel
is a FileNotFoundError the first time an installed (non-editable) dggen is run. The suite normally
runs against an editable install, where that can never show up - hence building a real wheel.
(pip builds in an isolated environment, so this needs to be able to fetch setuptools.)
"""

from __future__ import annotations

import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

import pytest

from dggen import config

REPO = Path(__file__).resolve().parent.parent


@pytest.fixture(scope="module")
def wheel_names(tmp_path_factory):
    src = tmp_path_factory.mktemp("src")
    # Build from a scratch copy so the build's build/ and *.egg-info don't land in the repo.
    for name in ("pyproject.toml", "README.md", "LICENSE.md"):
        shutil.copy(REPO / name, src / name)
    shutil.copytree(REPO / "dggen", src / "dggen", ignore=shutil.ignore_patterns("__pycache__"))
    out = tmp_path_factory.mktemp("wheel")
    result = subprocess.run(
        [sys.executable, "-m", "pip", "wheel", ".", "--no-deps", "-q", "-w", str(out)],
        cwd=src,
        capture_output=True,
        text=True,
    )
    wheels = list(out.glob("dggen-*.whl"))
    assert result.returncode == 0 and wheels, f"wheel build failed:\n{result.stderr[-1500:]}"
    with zipfile.ZipFile(wheels[0]) as wheel:
        return set(wheel.namelist())


def _runtime_assets():
    """Every file config points at, as a path relative to the package root."""
    paths = [
        config.DEFAULT_FONT_FILE,
        config.OCR_FONT_FILE,
        config.FRONT_COVER_IMAGE,
        config.INSIDE_COVER_IMAGE,
        config.SHEET_FRONT_IMAGE,
        config.SHEET_BACK_IMAGE,
        config.DEFAULT_PROFESSIONS,
        config.DEFAULT_EQUIPMENT,
        config.DEFAULT_DISTINGUISHING,
        config.DEFAULT_EDUCATION_DATA,
        config.DEFAULT_EMPLOYER_DATA,
    ]
    paths += [p for p in config.POOLS_DIR.rglob("*") if p.is_file()]
    paths += config.DATA_DIR.glob("professions-*.json")
    pkg = Path(config.__file__).resolve().parent
    return sorted(Path(p).resolve().relative_to(pkg.parent).as_posix() for p in paths)


def test_wheel_contains_every_runtime_asset(wheel_names):
    assets = _runtime_assets()
    assert len(assets) > 30  # fonts, sheets, data files and every pool - not an empty glob
    missing = [asset for asset in assets if asset not in wheel_names]
    assert not missing, f"missing from the wheel: {missing[:10]}"


def test_wheel_leaves_out_dev_only_files(wheel_names):
    assert not [name for name in wheel_names if name.endswith(".pdf")]
