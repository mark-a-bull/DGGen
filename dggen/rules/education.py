"""Auto-generated education: a single "degree, institution year." sheet line, chosen to be
plausible for the character's profession and age.

Looked up by the profession's display label (lowercased), not its data key, since many different
profession-set keys across data/professions*.json (e.g. 'agent', 'cid', 'nsb-agent') share the
same real-world job and so the same label ('Federal Agent') - mirroring how find_profession()
already resolves -t/--type by label. Unknown labels fall back to the '_default' entry, so new
profession sets work without editing data/education.json.
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from dggen.character import Character
    from dggen.models import EducationData


def generate_education(char: Character, education_data: EducationData) -> None:
    if char.education:
        return  # --education override already applied in generate_demographics

    entry = education_data.professions.get(
        char.profession.label.lower(), education_data.professions["_default"],
    )

    # Only tiers the character is old enough to have completed. Iterating entry.tiers (a dict, so
    # insertion-ordered) rather than a set keeps the weighted choice's RNG draw order stable
    # across processes.
    eligible = {
        tier: weight
        for tier, weight in entry.tiers.items()
        if education_data.tier_defaults[tier].grad_age <= char.age
    }
    if not eligible:
        return  # too young for any tier this profession defines; leave the field blank

    tier_name = char.rng.choices(list(eligible), weights=list(eligible.values()), k=1)[0]
    tier = education_data.tier_defaults[tier_name]

    pool_name = entry.institution_pool_overrides.get(tier_name, tier.institution_pool)
    institution = char.rng.choice(education_data.institutions[pool_name])
    field = char.rng.choice(entry.fields) if entry.fields else ""
    grad_year = datetime.now().year - (char.age - tier.grad_age)

    # Degree phrasing ("B.S." vs "B.A.") is picked by field, not RNG, so it stays consistent
    # with the subject (never "B.A. Computer Science"). Tiers with only one phrasing (jd, md,
    # academy, ...) just use "default".
    if field and "science" in tier.templates:
        variant = "science" if field in education_data.science_fields else "arts"
    else:
        variant = "default"
    template = tier.templates.get(variant) or next(iter(tier.templates.values()))

    char.education = template.format(field=field, institution=institution, year=grad_year) + "."
