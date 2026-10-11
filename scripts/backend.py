"""Older name for the site's door to Statement Map's export; see scripts/reader.py.

Kept so that existing callers (sync_readme.py and older page builders) read the
same checked packets. load() returns the checked Reader for the release.
"""
from __future__ import annotations

from reader import Reader, ReaderError, load  # noqa: F401
