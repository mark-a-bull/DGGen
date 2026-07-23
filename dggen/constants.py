"""Game-rule constants shared by the character and rules modules.

Kept dependency-free so both `character.py` and `rules/*` can import it without cycles.
"""

from __future__ import annotations

MONTHS = ("JAN", "FEB", "MAR", "APR", "MAY", "JUN", "JUL", "AUG", "SEP", "OCT", "NOV", "DEC")

# Chance (percent) that a profession's suggested bonus skill is considered for a boost.
SUGGESTED_BONUS_CHANCE = 75

PHYSICAL_STATS = ["strength", "constitution", "dexterity"]
STATS = [*PHYSICAL_STATS, "intelligence", "power", "charisma"]

# Pre-set stat arrays a character may be assigned (before shuffling), plus a rolled array.
STAT_POOLS = [
    [13, 13, 12, 12, 11, 11],
    [15, 14, 12, 11, 10, 10],
    [17, 14, 13, 10, 10, 8],
]

DEFAULT_SKILLS = {
    "accounting": 10,
    "alertness": 20,
    "athletics": 30,
    "bureaucracy": 10,
    "criminology": 10,
    "disguise": 10,
    "dodge": 30,
    "drive": 20,
    "firearms": 20,
    "first aid": 10,
    "heavy machinery": 10,
    "history": 10,
    "humint": 10,
    "melee weapons": 30,
    "navigate": 10,
    "occult": 10,
    "persuade": 20,
    "psychotherapy": 10,
    "ride": 10,
    "search": 20,
    "stealth": 10,
    "survival": 10,
    "swim": 20,
    "unarmed combat": 40,
}

ALL_BONUS = [
    "accounting",
    "alertness",
    "anthropology",
    "archeology",
    "art1",
    "artillery",
    "athletics",
    "bureaucracy",
    "computer science",
    "craft1value",
    "criminology",
    "demolitions",
    "disguise",
    "dodge",
    "drive",
    "firearms",
    "first aid",
    "forensics",
    "heavy machinery",
    "heavy weapons",
    "history",
    "humint",
    "law",
    "medicine",
    "melee weapons",
    "militaryscience1value",
    "navigate",
    "occult",
    "persuade",
    "pharmacy",
    "pilot1value",
    "psychotherapy",
    "ride",
    "science1value",
    "search",
    "sigint",
    "stealth",
    "surgery",
    "survival",
    "swim",
    "unarmed combat",
    "language1",
]

# The footnote indicator glyphs, cycled as footnotes are registered.
FOOTNOTE_MARKERS = [
    "*", "†", "‡", "§", "¶", "**", "††", "‡‡", "§§", "¶¶", "***", "†††", "‡‡‡", "§§§",
]
