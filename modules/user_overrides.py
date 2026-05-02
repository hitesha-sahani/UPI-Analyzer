"""
modules/user_overrides.py
─────────────────────────
Per-user merchant → category overrides.

Storage layout  (config/user_overrides.json)
────────────────────────────────────────────
{
  "user_1": {
    "rahul":      "P2P Transfers",
    "mom":        "P2P Transfers"
  },
  "user_2": {
    "rahul":      "Food & Dining"
  }
}

Keys are the lowercase output of _extract_merchant(), e.g. "rahul", "swiggy",
"local kirana shop".  They are produced once by categorizer.py and stored here
verbatim — so lookups are always consistent.

Caching
───────
The JSON file is read from disk at most ONCE per Streamlit session (module load).
All subsequent reads hit the in-memory dict.  Writes update both the dict and
the file atomically so the cache never goes stale.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

# ── Path ──────────────────────────────────────────────────────────────────────
_OVERRIDES_PATH = Path(__file__).parent.parent / "config" / "user_overrides.json"

# ── Module-level cache ────────────────────────────────────────────────────────
# Populated on first call to any public function; never re-read from disk
# unless invalidate_cache() is called explicitly.
_cache: dict | None = None


# ── Internal helpers ──────────────────────────────────────────────────────────

def _load() -> dict:
    """Return the full overrides dict, reading from disk only if needed."""
    global _cache
    if _cache is None:
        if _OVERRIDES_PATH.exists():
            with open(_OVERRIDES_PATH, "r", encoding="utf-8") as f:
                _cache = json.load(f)
        else:
            _cache = {}
    return _cache


def _save(data: dict) -> None:
    """Write `data` to disk and keep the cache in sync."""
    global _cache
    _OVERRIDES_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(_OVERRIDES_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    _cache = data  # update cache in-place


# ── Public API ────────────────────────────────────────────────────────────────

def get_override(user_id: str, merchant_key: str) -> str | None:
    """
    Return the user's saved category for `merchant_key`, or None if not set.

    Parameters
    ----------
    user_id      : e.g. "user_1"
    merchant_key : lowercase merchant string, e.g. "rahul" or "swiggy"
    """
    data = _load()
    return data.get(user_id, {}).get(merchant_key)


def get_user_map(user_id: str) -> dict[str, str]:
    """Return the full merchant→category dict for one user (may be empty)."""
    return dict(_load().get(user_id, {}))


def save_one(user_id: str, merchant_key: str, category: str) -> None:
    """Persist a single override and update the cache."""
    data = _load()
    data.setdefault(user_id, {})[merchant_key] = category
    _save(data)


def save_bulk(user_id: str, mapping: dict[str, str]) -> None:
    """
    Persist multiple overrides for one user in a single file write.

    Parameters
    ----------
    mapping : { "rahul": "P2P Transfers", "mom": "P2P Transfers", ... }
    """
    data = _load()
    data.setdefault(user_id, {}).update(mapping)
    _save(data)


def invalidate_cache() -> None:
    """Force the next read to reload from disk (rarely needed)."""
    global _cache
    _cache = None