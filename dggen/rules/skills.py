"""Skills: default skills, professional fixed/picked skills, bonds, and bonus-skill boosts."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from dggen.constants import ALL_BONUS, DEFAULT_SKILLS, SUGGESTED_BONUS_CHANCE

if TYPE_CHECKING:
    from dggen.character import Character

logger = logging.getLogger("dggen")


def generate_skills(char: Character) -> None:
    # Default skills.
    char.d.update(DEFAULT_SKILLS)

    # Professional skills - fixed.
    for skill, score in char.profession.skills.fixed.items():
        char.d[skill] = score
        logger.debug("%s, set fixed professional skill %s to %s", char, skill, score)

    # Professional skills - a random subset of the "possible" skills.
    for skill, score in char.rng.sample(
        list(char.profession.skills.possible.items()),
        char.profession.skills.possible_count,
    ):
        char.d[skill] = score
        logger.debug("%s, set picked professional skill %s to %s", char, skill, score)

    for i in range(char.profession.bonds):
        char.d[f"bond{i}"] = char.d["charisma"]

    generate_bonus_skills(char)


def generate_bonus_skills(char: Character) -> None:
    potential_bonus_skills = [
        s for s in char.profession.skills.bonus if char.rng.randint(1, 100) <= SUGGESTED_BONUS_CHANCE
    ] + char.rng.sample(ALL_BONUS, len(ALL_BONUS))
    apply_bonuses(char, potential_bonus_skills, 8, 20, 80)


def apply_bonuses(
    char: Character,
    potential_bonus_skills: list[str],
    number_of_skills_to_boost: int,
    boost_by_percentile: int,
    max_skill_level: int,
) -> None:
    bonuses_applied = 0
    while bonuses_applied < number_of_skills_to_boost:
        skill = potential_bonus_skills.pop(0)
        boosted = char.d.get(skill, 0) + boost_by_percentile
        if boosted <= max_skill_level:
            char.d[skill] = boosted
            bonuses_applied += 1
            char.bonus_skills.append(skill)
            logger.debug(
                "%s, boosted bonus skill %s by %s%% to %s",
                char,
                skill,
                boost_by_percentile,
                boosted,
            )
        else:
            logger.debug("%s, Skipped boost - %s already at %s", char, skill, char.d.get(skill, 0))
