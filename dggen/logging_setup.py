"""Logger and warnings configuration, keyed off the -v/--verbosity count (0-3)."""

from __future__ import annotations

import logging
import sys
import warnings
from typing import TextIO


def init_logger(verbosity: int, stream: TextIO = sys.stdout) -> None:
    is_not_debug = verbosity <= 2
    level = (
        [logging.ERROR, logging.WARNING, logging.INFO][verbosity] if is_not_debug else logging.DEBUG
    )
    log_format = (
        "%(message)s"
        if is_not_debug
        else "%(asctime)s %(levelname)-8s %(name)s %(module)s.py:%(funcName)s():%(lineno)d %(message)s"
    )
    logging.basicConfig(level=level, format=log_format, stream=stream)
    if is_not_debug:
        warnings.filterwarnings("ignore")
