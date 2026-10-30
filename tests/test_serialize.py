"""Serialization keeps display text intact; fitting it to the sheet is the PDF layer's job."""

from __future__ import annotations

from dggen.equipped import EquippedWeapon
from dggen.serialize import _weapon_fields


def test_long_weapon_names_are_not_truncated():
    """Cutting names at 15 characters turned both "Grenade launcher" and "Grenade machine gun"
    into "Grenade…", so two different weapons became indistinguishable on the sheet."""
    names = ("Grenade launcher", "Grenade machine gun", "Flash-bang Grenade")
    shown = [_weapon_fields(0, EquippedWeapon(name=name, roll=50))["weapon0"] for name in names]
    assert shown == list(names)
