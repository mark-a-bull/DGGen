"""A built wheel must carry the data files the package reads at runtime.

`dggen.config` resolves every asset relative to the package, so anything missing from the wheel
is a FileNotFoundError the first time an installed (non-editable) dggen is run. The suite normally
runs against an editable install, where that can never show up - hence building a real wheel.
(pip builds in an isolated environment, so this needs to be able to fetch setuptools.)
"""

from __future__ import annotations

import re
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

import pytest
from packaging.requirements import Requirement

import dggen
from dggen import appearance, config

REPO = Path(__file__).resolve().parent.parent


@pytest.fixture(scope="module")
def built_wheel(tmp_path_factory):
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
    return wheels[0]


@pytest.fixture(scope="module")
def wheel_names(built_wheel):
    with zipfile.ZipFile(built_wheel) as wheel:
        return set(wheel.namelist())


def _runtime_assets():
    """Every file config points at, as a path relative to the package root."""
    paths = [
        appearance.DEFAULT_FONT_FILE,
        appearance.OCR_FONT_FILE,
        appearance.FRONT_COVER_IMAGE,
        appearance.INSIDE_COVER_IMAGE,
        appearance.SHEET_FRONT_IMAGE,
        appearance.SHEET_BACK_IMAGE,
        config.DEFAULT_PROFESSIONS,
        config.DEFAULT_EQUIPMENT,
        config.DEFAULT_DISTINGUISHING,
        config.DEFAULT_SHEET_LAYOUT,
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


def _declared(path: str) -> list[str]:
    """The requirement strings in a requirements.txt, or [project].dependencies in pyproject."""
    text = (REPO / path).read_text(encoding="utf-8")
    if path.endswith(".toml"):
        block = re.search(r"^dependencies = \[(.*?)\]", text, re.DOTALL | re.MULTILINE)
        assert block, "no [project] dependencies found"
        code = "\n".join(
            line for line in block.group(1).splitlines() if not line.lstrip().startswith("#")
        )
        return re.findall(r'"([^"]+)"', code)
    return [line.strip() for line in text.splitlines() if line.strip() and line[0] != "#"]


@pytest.mark.parametrize("path", ["pyproject.toml", "requirements.txt"])
def test_pillow_is_floored_at_a_release_without_known_advisories(path):
    """reportlab pulls Pillow in without a useful floor, so an old, vulnerable Pillow would satisfy
    the declared dependencies. 13.0.0 fixes the 39 advisories open against 12.x. It needs Python
    3.11+, which is the minimum this project supports, so the floor needs no condition."""
    [requirement] = [r for r in _declared(path) if r.lower().startswith("pillow")]
    assert re.fullmatch(r"pillow>=13(\.\d+)*", requirement), requirement


def test_the_wheel_marks_the_package_as_typed(wheel_names):
    """`py.typed` (PEP 561) is what tells type checkers to use dggen's inline annotations."""
    assert "dggen/py.typed" in wheel_names


def test_the_requirements_file_mirrors_pyproject():
    """pyproject.toml is the single source for the runtime dependencies; requirements.txt (used by
    `pip install -r` and `pip-audit -r`) is a copy of it, so it must not drift."""
    declared = sorted(str(Requirement(r)) for r in _declared("pyproject.toml"))
    mirrored = sorted(str(Requirement(r)) for r in _declared("requirements.txt"))
    assert mirrored == declared, "requirements.txt should contain exactly:\n" + "\n".join(declared)


def test_the_version_has_a_single_source(built_wheel):
    """It used to be written in both pyproject.toml and dggen/__init__.py."""
    text = (REPO / "pyproject.toml").read_text(encoding="utf-8")
    assert re.search(r'^dynamic = \["version"\]', text, re.MULTILINE)
    assert not re.search(r'^version = "', text, re.MULTILINE)  # no second, static copy
    with zipfile.ZipFile(built_wheel) as wheel:
        name = next(n for n in wheel.namelist() if n.endswith(".dist-info/METADATA"))
        metadata = wheel.read(name).decode("utf-8").replace("\r\n", "\n")
    assert f"Version: {dggen.__version__}\n" in metadata


def _pyproject() -> str:
    return (REPO / "pyproject.toml").read_text(encoding="utf-8")


def test_the_python_floor_and_the_tool_targets_agree():
    """Python 3.10 is dropped (Pillow 13, which fixes the open advisories, needs 3.11+). The minimum
    version, mypy's target and ruff's target are written in three places; they must not drift."""
    text = _pyproject()
    assert re.search(r'^requires-python = ">=3\.11"$', text, re.MULTILINE)
    assert re.search(r'^python_version = "3\.11"$', text, re.MULTILINE)  # [tool.mypy]
    assert re.search(r'^target-version = "py311"$', text, re.MULTILINE)  # [tool.ruff]


def test_the_dev_extra_keeps_pip_itself_current():
    """pip has had advisories fixed in 26.2.0. It lives in the dev extra, not the runtime
    dependencies: a runtime requirement on pip would make `pip install dggen` fail for anyone
    on Windows with an older pip (pip cannot upgrade itself through pip.exe)."""
    dev = re.search(r"^dev = \[(.*?)\]", _pyproject(), re.DOTALL | re.MULTILINE)
    assert dev, "no dev extra"
    requirements = [Requirement(r) for r in re.findall(r'"([^"]+)"', dev.group(1))]
    [pip] = [r for r in requirements if r.name == "pip"]
    assert any(spec.version.startswith("26") for spec in pip.specifier)
    assert not [r for r in _declared("pyproject.toml") if r.lower().startswith("pip")]
