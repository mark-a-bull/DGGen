"""Configure the `dggen` logger from the -v/--verbosity count.

Diagnostics go to stderr, so stdout stays what the user asked for (the character summary). Warnings
are shown by default: the ones this code emits (a kit that doesn't fit the sheet, running out of
footnote markers) describe things silently missing from the output, which is not something to hide
behind a flag. Only the `dggen` logger is configured - never the root logger, and never the
process-wide `warnings` filters, which would also hide every dependency's warnings.
"""

from __future__ import annotations

import logging
import sys
from typing import TextIO

# -v adds information, -vv debug, -vvv debug with timestamps and source locations.
_LEVELS = (logging.WARNING, logging.INFO, logging.DEBUG, logging.DEBUG)
_PLAIN = "%(message)s"
_DETAILED = (
    "%(asctime)s %(levelname)-8s %(name)s %(module)s.py:%(funcName)s():%(lineno)d %(message)s"
)
# Marks the handler `init_logger` installed, so calling it again replaces it instead of adding one.
_OURS = "_dggen_cli_handler"


def init_logger(verbosity: int, stream: TextIO | None = None) -> None:
    """Route `dggen` logging to `stream` (default: stderr, looked up now, not at import)."""
    logger = logging.getLogger("dggen")
    for handler in [h for h in logger.handlers if getattr(h, _OURS, False)]:
        logger.removeHandler(handler)

    handler = logging.StreamHandler(stream or sys.stderr)
    setattr(handler, _OURS, True)
    handler.setFormatter(logging.Formatter(_DETAILED if verbosity >= 3 else _PLAIN))
    logger.addHandler(handler)
    logger.setLevel(_LEVELS[min(max(verbosity, 0), 3)])
