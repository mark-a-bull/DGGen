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


def skill_checks_at_age(
    age: int,
    earned_at_start: int = 4,
    start_age: int = 25,
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
    skills_to_check = set(
        list(char.profession.skills.fixed.keys())
        + list(char.profession.skills.possible.keys())
        + char.bonus_skills,
    )
    skill_checks = floor(sum(skill_checks_at_age(y) for y in range(25, char.age + 1)))
    for skill in skills_to_check:
        if isinstance(char.d.get(skill, 0), int) and char.d.get(skill, 0) > 0:
            original = char.d[skill]
            for _ in range(skill_checks):
                current = char.d[skill]
                roll = char.rng.randint(1, 100)
                if roll > current or roll == 100:
                    char.d[skill] += 1
            logger.debug(
                "%s, veterancy experience %s, %s checks, from %s to %s",
                char,
                skill,
                skill_checks,
                original,
                char.d[skill],
            )


def veterancy_stat_losses(char: Character) -> None:
    losses = 0
    if 40 <= char.age <= 49:
        losses = 1
    elif 50 <= char.age <= 59:
        losses = 2
    elif 60 <= char.age <= 69:
        losses = 4
    elif 70 <= char.age <= 79:
        losses = 8
    elif 80 <= char.age <= 89:
        losses = 16
    elif char.age >= 90:
        losses = 32
    while losses and not all(char.d[stat] <= 1 for stat in PHYSICAL_STATS):
        target = char.rng.choice(PHYSICAL_STATS)
        if char.d[target] > 1:
            char.d[target] -= 1
            losses -= 1
            logger.debug("%s, %s decreased by 1 to %s by veterancy", char, target, char.d[target])


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
    for i, description in enumerate(damage):
        char.e[f"detail{i}"] = description


def extreme_violence_changes(char: Character, damage: list[str]) -> None:
    damage.append("• Extreme Violence")
    char.d["occult"] += 10
    char.san_lost += 5
    char.d["charisma"] -= 3
    for i in range(char.profession.bonds):
        if f"bond{i}" in char.d:
            char.d[f"bond{i}"] -= 3
    char.adapted_to_violence = 3


def captivity_or_imprisonment_changes(char: Character, damage: list[str]) -> None:
    damage.append("• Captivity or Imprisonment")
    char.d["occult"] += 10
    char.san_lost += 5
    char.d["power"] -= 3
    char.adapted_to_helplessness = 3


def hard_experience_changes(char: Character, damage: list[str]) -> None:
    damage.append("• Hard Experience")
    char.d["occult"] += 10
    potential_bonus_skills = char.rng.sample(ALL_BONUS, len(ALL_BONUS))
    apply_bonuses(char, potential_bonus_skills, 5, 10, 90)
    char.san_lost += 5
    del char.d[f"bond{char.profession.bonds - 1}"]


def things_man_was_not_meant_to_know_changes(char: Character, damage: list[str]) -> None:
    damage.append("• Things Man Was Not Meant to Know")
    char.d["unnatural"] = char.d.get("unnatural", 0) + 10
    char.d["occult"] += 20
    char.san_lost += char.d["power"]
    char.d["disorder0"] = "Disorder: " + char.rng.choice(
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
