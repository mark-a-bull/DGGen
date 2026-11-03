"""`config` is where the data lives; how the sheet looks is `appearance`."""

from __future__ import annotations

from dggen import appearance, config

APPEARANCE = (
    "PAGE_WIDTH",
    "PAGE_HEIGHT",
    "PAGE_SIZE",
    "TEXT_COLOR",
    "DEFAULT_FONT",
    "OCR_FONT",
    "DEFAULT_FONT_FILE",
    "OCR_FONT_FILE",
    "FRONT_COVER_IMAGE",
    "INSIDE_COVER_IMAGE",
    "SHEET_FRONT_IMAGE",
    "SHEET_BACK_IMAGE",
)


def test_presentation_constants_live_in_appearance_not_config():
    for name in APPEARANCE:
        assert hasattr(appearance, name), name
        assert not hasattr(config, name), f"{name} should not be in config any more"


def test_appearance_assets_exist():
    for name in ("DEFAULT_FONT_FILE", "OCR_FONT_FILE", "FRONT_COVER_IMAGE", "SHEET_FRONT_IMAGE"):
        assert getattr(appearance, name).is_file(), name


def test_appearance_assets_are_resolved_from_the_configured_data_dir():
    assert appearance.DEFAULT_FONT_FILE.parent == config.DATA_DIR


def test_config_keeps_the_paths_and_defaults():
    assert config.DEFAULT_PROFESSIONS.parent == config.DATA_DIR
    assert config.POOLS_DIR == config.DATA_DIR / "pools"
    assert config.DEFAULT_TOWNS == "towns/us"
