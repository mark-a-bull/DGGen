"""DGGen - character sheet generator for the Delta Green RPG.

The package is organised in four layers that only communicate across narrow seams:

- data:         models.py, data.py         (JSON/CSV -> typed objects)
- domain/rules: character.py, rules/        (game rules -> field dicts on a Character)
- presentation: pdf.py                      (field dicts -> PDF via reportlab)
- interface:    cli.py                      (argparse + orchestration)

Randomness is funnelled through a single seedable `Rng` (rng.py) so generation is
reproducible and therefore testable.
"""

__version__ = "2.0"
