"""Auto-generated employer, looked up by profession label like rules/education.py.

Only fills in char.employer if it is still blank after generate_demographics - i.e. neither
--employer nor the profession's own employer/division (set by variant profession files like
data/professions-fbi.json, e.g. "FBI, CID") provided one. That precedence must never be
disturbed: those variant files intentionally hardcode real organisational context that this
module must not overwrite.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from dggen.character import Character
    from dggen.models import EmployerData


def generate_employer(char: Character, employer_data: EmployerData) -> None:
    if char.employer:
        return  # --employer override, or the profession's own employer/division, already set

    entry = employer_data.professions.get(
        char.profession.label.lower(), employer_data.professions["_default"],
    )
    option = char.rng.choices(entry.options, weights=[o.weight for o in entry.options], k=1)[0]

    if option.literal is not None:
        char.employer = option.literal
    elif option.pool is not None:
        char.employer = char.data.pools.choice(option.pool, char.rng)
    elif option.template is not None:
        city = char.town.split(",")[0].strip()
        char.employer = option.template.format(city=city)
    else:
        char.employer = ""
