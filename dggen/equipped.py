"""Structured result of equipping a weapon.

Distinct from `models.Weapon` (which mirrors the equipment JSON): this holds the resolved,
per-character values - the computed skill roll, the effective damage modifier (after damage
bonus), and the footnote markers already assigned during generation. The presentation layer
formats these into sheet strings; the domain never builds those strings itself.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class EquippedWeapon:
    name: str
    roll: int
    base_range: str | None = None
    ap: int | None = None
    ammo: int | None = None
    kill_radius: str | None = None

    has_lethality: bool = False
    lethality_rating: int | None = None
    lethality_marker: str | None = None

    note_markers: list[str] = field(default_factory=list)

    has_damage: bool = False
    damage_dice: int | None = None
    damage_die_type: int | None = None
    damage_modifier: int = 0
    damage_marker: str | None = None
