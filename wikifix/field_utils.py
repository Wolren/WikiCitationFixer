"""Shared field utility functions for citation template parameter manipulation.

Consolidates duplicate ``_has_field`` / ``_get_field`` / ``_remove_field`` /
``_add_field`` / ``_set_field`` implementations across multiple modules
into a single location with LRU-cached compiled patterns.
"""

from __future__ import annotations

import re
from functools import lru_cache

__all__ = [
    "has_field",
    "get_field",
    "remove_field",
    "add_field",
    "set_field",
]


@lru_cache(maxsize=256)
def _exists_pattern(field: str) -> re.Pattern[str]:
    return re.compile(rf"\|\s*{re.escape(field)}\s*=")


@lru_cache(maxsize=256)
def _get_pattern(field: str) -> re.Pattern[str]:
    return re.compile(rf"\|\s*{re.escape(field)}\s*=\s*([^|]+)")


@lru_cache(maxsize=256)
def _remove_pattern(field: str) -> re.Pattern[str]:
    return re.compile(rf"\|\s*{re.escape(field)}\s*=[^|]+")


def has_field(text: str, field: str) -> bool:
    """Check whether a parameter already exists in the citation body."""
    return _exists_pattern(field).search(text) is not None


def get_field(text: str, field: str) -> str | None:
    """Extract the value of a parameter from the citation body."""
    m = _get_pattern(field).search(text)
    return m.group(1).strip() if m else None


def remove_field(text: str, field: str, *, count: int = 1) -> str:
    """Remove a parameter and its value from the citation body."""
    return _remove_pattern(field).sub("", text, count=count)


def add_field(text: str, name: str, value: str, *, force: bool = False) -> str:
    """Append or replace a parameter in the citation body.

    When *force* is False (default), an existing parameter is kept unchanged.
    When *force* is True, the existing parameter is removed before appending.
    """
    if has_field(text, name):
        if not force:
            return text
        text = remove_field(text, name)
    return text + f" |{name}={value}"


def set_field(text: str, field: str, new_value: str) -> str:
    """Replace the entire ``|field=...`` parameter with a clean version in-place.

    Unlike *add_field* (which appends), this edits the matched parameter
    in its original position within the body.
    """
    m = _get_pattern(field).search(text)
    if not m:
        return text
    old = m.group(0).rstrip()
    return text.replace(old, f"| {field} = {new_value}", 1)
