"""Character-generation rules, split by concern.

Each module exposes functions that take a `Character` (and use its `.rng`) and mutate it in place:

- stats:     stat rolling and derived attributes
- skills:    default / professional / bonus skills
- veterancy: age-based experience, stat losses, Damaged Veteran effects
- equipment: weapons, gear, footnotes

They import `Character` only for type-checking, so `character.py` can import them without a cycle.
"""
