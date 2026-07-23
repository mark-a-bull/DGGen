"""Enable `python -m dggen`."""

from __future__ import annotations

import sys

from dggen.cli import main

if __name__ == "__main__":
    sys.exit(main())
