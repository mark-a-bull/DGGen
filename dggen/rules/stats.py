"""Statistics: rolling the six stats and computing derived attributes."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from dggen.constants import STAT_POOLS, STATS

if TYPE_CHECKING:
    from dggen.character import Character

logger = logging.getLogger("dggen")


def damage_bonus(strength: int) -> int:
    """Delta Green damage bonus derived from Strength."""
    return ((strength - 1) >> 2) - 2


def generate_stats(char: Character) -> None:
    rolled = [[sum(sorted([char.rng.randint(1, 6) for _ in range(4)])[1:]) for _ in range(6)]]
    # Copy the chosen pool before shuffling: choice() may return one of the shared STAT_POOLS
    # lists, and shuffling in place would mutate that module constant (breaking reproducibility
    # across characters that share a seed).
    pool = list(char.rng.choice(STAT_POOLS + rolled))
    char.rng.shuffle(pool)
    for score, stat in zip(pool, STATS, strict=False):
        char.d[stat] = score
        logger.debug("%s,stat %s is %s", char, stat, score)


def generate_derived_attributes(char: Character) -> None:
    char.d["hitpoints"] = round((char.d["strength"] + char.d["constitution"]) / 2.0)
    char.d["willpower"] = char.d["power"]
    char.d["sanity"] = char.d["power"] * 5
    if char.san_lost:
        char.d["current_sanity"] = (char.d["power"] * 5) - char.san_lost
    char.d["breaking point"] = char.d["sanity"] - char.d["power"]
    char.damage_bonus = damage_bonus(char.d["strength"])
    char.d["damage bonus"] = "DB=%d" % char.damage_bonus
    for stat in STATS:
        score = char.d[stat]
        char.d[f"{stat}_x5"] = score * 5
        char.d[f"{stat}_distinguishing"] = char.distinguishing(stat, score)
    char.d["violence"] = "  ".join("X" for _ in range(char.adapted_to_violence))
    char.d["helplessness"] = "  ".join("X" for _ in range(char.adapted_to_helplessness))
