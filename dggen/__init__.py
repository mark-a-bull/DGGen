"""DGGen - character generator for the Delta Green RPG, as a library and a command line tool.

Quick start::

    import dggen

    data = dggen.load_data(dggen.DataSources())          # read the bundled data files
    rng = dggen.Rng(42)                                   # one seed reproduces everything
    agent = dggen.find_profession(data.professions, "Federal Agent")
    options = dggen.GenerationOptions(name_override="Dr. Ada Quill")

    for profession, character in dggen.generate_roster(data, rng, [agent], options, count=1):
        print(dggen.format_details(character))            # readable text
        fields = dggen.to_front_fields(character)          # or the sheet's field values

Everything in ``__all__`` is the supported API; the rest of the package is internal and may change.
The names are imported on first use, so ``import dggen`` (e.g. to read ``__version__``) stays cheap
and does not load reportlab or Faker.

The package is organised in layers that only communicate across narrow seams:

- data:         models.py, data.py, pools.py, validate.py   (JSON/CSV -> typed, checked objects)
- domain/rules: character.py, rules/                         (game rules -> a Character)
- serialization: serialize.py, summary.py                    (a Character -> sheet fields / text)
- presentation: pdf.py, sinks.py, layout.py                  (fields -> PDF via reportlab)
- interface:    cli.py                                       (argparse + orchestration)

Randomness is funnelled through a single seedable ``Rng`` (rng.py) so generation is reproducible
and therefore testable.
"""

from __future__ import annotations

import importlib
from typing import TYPE_CHECKING, Any

__version__ = "2.0"

# public name -> the module that defines it (imported on first access, then cached)
_EXPORTS = {
    "Character": "dggen.character",
    "Data": "dggen.models",
    "DataError": "dggen.errors",
    "DataSources": "dggen.options",
    "GenerationOptions": "dggen.options",
    "InvalidLocaleError": "dggen.data",
    "PoolError": "dggen.pools",
    "Profession": "dggen.models",
    "ProfessionNotFoundError": "dggen.data",
    "Rng": "dggen.rng",
    "TemplateError": "dggen.text",
    "find_profession": "dggen.data",
    "format_details": "dggen.summary",
    "generate_character": "dggen.roster",
    "generate_roster": "dggen.roster",
    "load_data": "dggen.data",
    "to_back_fields": "dggen.serialize",
    "to_front_fields": "dggen.serialize",
}

# An explicit list (not derived from _EXPORTS) so tools can read it; a test keeps the two in step.
__all__ = [
    "Character",
    "Data",
    "DataError",
    "DataSources",
    "GenerationOptions",
    "InvalidLocaleError",
    "PoolError",
    "Profession",
    "ProfessionNotFoundError",
    "Rng",
    "TemplateError",
    "__version__",
    "find_profession",
    "format_details",
    "generate_character",
    "generate_roster",
    "load_data",
    "to_back_fields",
    "to_front_fields",
]

if TYPE_CHECKING:  # for type checkers and IDEs; at runtime the names load lazily below
    from dggen.character import Character
    from dggen.data import (
        InvalidLocaleError,
        ProfessionNotFoundError,
        find_profession,
        load_data,
    )
    from dggen.errors import DataError
    from dggen.models import Data, Profession
    from dggen.options import DataSources, GenerationOptions
    from dggen.pools import PoolError
    from dggen.rng import Rng
    from dggen.roster import generate_character, generate_roster
    from dggen.serialize import to_back_fields, to_front_fields
    from dggen.summary import format_details
    from dggen.text import TemplateError


def __getattr__(name: str) -> Any:
    module = _EXPORTS.get(name)
    if module is None:
        raise AttributeError(f"module 'dggen' has no attribute {name!r}")
    value = getattr(importlib.import_module(module), name)
    globals()[name] = value  # cache, so the next access is a plain attribute lookup
    return value


def __dir__() -> list[str]:
    return sorted([*globals(), *_EXPORTS])
