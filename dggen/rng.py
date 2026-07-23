"""A single, seedable source of randomness for the whole generator.

`Rng` subclasses `random.Random`, so it exposes `randint`, `choice`, `choices`, `sample` and
`shuffle` with exactly the semantics the code relied on when it used the module-level `random.*`
functions. Threading one instance through generation (instead of the global RNG) makes output
reproducible: construct `Rng(seed)` and the same seed yields the same characters, which is what
lets the domain layer be tested by asserting on concrete output.

An unseeded `Rng()` is as nondeterministic as the old code, so default behaviour is unchanged.
"""

from __future__ import annotations

import random


class Rng(random.Random):
    """Seedable RNG. `Rng(None)` (the default) is nondeterministic; `Rng(1234)` is repeatable."""
