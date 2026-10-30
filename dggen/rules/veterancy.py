"""Veterancy: age-based experience gains, physical stat losses, and Damaged Veteran effects
(Agent's Handbook p.38)."""

from __future__ import annotations

import logging
from math import floor
from typing import TYPE_CHECKING

from dggen.constants import ALL_BONUS, PHYSICAL_STATS
from dggen.rules.skills import apply_bonuses

if TYPE_CHECKING:
    from dggen.character import Character

logger = logging.getLogger("dggen")

# Experience starts accruing the year the agent turns 25 (AH p.38).
VETERANCY_START_AGE = 25


def skill_checks_at_age(
    age: int,
    earned_at_start: int = 4,
    start_age: int = VETERANCY_START_AGE,
    halve_rate: int = 10,
) -> float:
    """Skill checks earned in the year the agent turns `age`; halves every `halve_rate` years."""
    return earned_at_start * (1 / 2 ** ((age - start_age) / halve_rate))


def apply_veterancy(char: Character, damaged: bool) -> None:
    veterancy_skill_boosts(char)
    veterancy_stat_losses(char)
    if damaged:
        damaged_veteran_changes(char)


def veterancy_skill_boosts(char: Character) -> None:
    # dict.fromkeys dedupes while preserving first-seen order. A plain set() would iterate in an
    # order that varies across processes (string hash randomisation), which would make the
    # per-skill experience rolls consume the RNG in a different order each run - i.e. --seed would
    # not actually reproduce a veteran. Ordering it deterministically fixes that.
    # Only skills the character really has as professional/bonus skills earn experience: an
    # optional (`possible`) skill that wasn't picked is merely a default skill here.
    skills_to_check = list(
        dict.fromkeys(
            list(char.profession.skills.fixed.keys()) + char.picked_skills + char.bonus_skills,
        ),
    )
    skill_checks = floor(
        sum(skill_checks_at_age(y) for y in range(VETERANCY_START_AGE, char.age + 1)),
    )
    for skill in skills_to_check:
        if char.skills.get(skill, 0) > 0:
            original = char.skills[skill]
            for _ in range(skill_checks):
                current = char.skills[skill]
                roll = char.rng.randint(1, 100)
                if roll > current or roll == 100:
                    char.skills[skill] += 1
            logger.debug(
                "%s, veterancy experience %s, %s checks, from %s to %s",
                char,
                skill,
                skill_checks,
                original,
                char.skills[skill],
            )


def stat_losses_at_age(age: int) -> int:
    """Physical stat points lost to age: 1 from 40, then doubling each decade, capped at 32."""
    if age < 40:
        return 0
    return 1 << min((age - 40) // 10, 5)


def veterancy_stat_losses(char: Character) -> None:
    losses = stat_losses_at_age(char.age)
    while losses and not all(char.stats[stat] <= 1 for stat in PHYSICAL_STATS):
        target = char.rng.choice(PHYSICAL_STATS)
        if char.stats[target] > 1:
            char.stats[target] -= 1
            losses -= 1
            logger.debug(
                "%s, %s decreased by 1 to %s by veterancy",
                char,
                target,
                char.stats[target],
            )


def damaged_veteran_changes(char: Character) -> None:
    damage_count = char.rng.choices(range(5), weights=[80, 10, 5, 4, 1])[0]
    if not damage_count:
        return
    damage_methods = char.rng.sample(
        [
            extreme_violence_changes,
            captivity_or_imprisonment_changes,
            hard_experience_changes,
            things_man_was_not_meant_to_know_changes,
        ],
        k=damage_count,
    )
    damage: list[str] = ["Damaged Veteran:"]
    for method in damage_methods:
        logger.debug("%s, damaged veteran changes %s", char, method.__name__)
        method(char, damage)
        logger.debug(
            "%s, san lost, adapted_to_violence, adapted_to_helplessness now %s, %s, %s",
            char,
            char.san_lost,
            char.adapted_to_violence,
            char.adapted_to_helplessness,
        )
    char.damage_details = damage


def extreme_violence_changes(char: Character, damage: list[str]) -> None:
    damage.append("• Extreme Violence")
    char.skills["occult"] += 10
    char.san_lost += 5
    char.stats["charisma"] -= 3
    for i in range(char.profession.bonds):
        if i in char.bonds:
            char.bonds[i] -= 3
    char.adapted_to_violence = 3


def captivity_or_imprisonment_changes(char: Character, damage: list[str]) -> None:
    damage.append("• Captivity or Imprisonment")
    char.skills["occult"] += 10
    char.san_lost += 5
    char.stats["power"] -= 3
    char.adapted_to_helplessness = 3


def hard_experience_changes(char: Character, damage: list[str]) -> None:
    damage.append("• Hard Experience")
    char.skills["occult"] += 10
    potential_bonus_skills = char.rng.sample(ALL_BONUS, len(ALL_BONUS))
    apply_bonuses(char, potential_bonus_skills, 5, 10, 90)
    char.san_lost += 5
    del char.bonds[char.profession.bonds - 1]


def things_man_was_not_meant_to_know_changes(char: Character, damage: list[str]) -> None:
    damage.append("• Things Man Was Not Meant to Know")
    char.skills["unnatural"] = char.skills.get("unnatural", 0) + 10
    char.skills["occult"] += 20
    char.san_lost += char.stats["power"]
    char.disorder = char.rng.choice(
        [
            "Amnesia",
            "Depersonalization",
            "Depression",
            "Dissociative Identity",
            "Fugues",
            "Megalomania",
            "Paranoia",
            "Sleep Disorder",
        ],
    )
