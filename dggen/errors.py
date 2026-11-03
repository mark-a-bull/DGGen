"""Errors shared across layers (kept here so low-level modules can raise them without cycles)."""

from __future__ import annotations


class DataError(Exception):
    """A data file is malformed or inconsistent (a bad structure, a reference to nothing)."""
