#!/usr/bin/env python3
"""Backwards-compatible entry point.

The generator was refactored into the `dggen` package; this shim keeps `./generator.py ...`
(and every README recipe) working. Prefer `python -m dggen` or the installed `dggen` command.
"""

from __future__ import annotations

import sys

from dggen.cli import main

if __name__ == "__main__":
    sys.exit(main())
