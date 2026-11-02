"""Format raw valuation IDs into professional VAL-YYYY-XXXX references.

Three Towers Capital regression: the original report rendered the raw
``00000000-0000-4000-8000-000000000001`` UUID on every page header. That
makes a deliverable look unfinished. This module converts unformatted UUIDs
into ``VAL-{year}-{first 4 hex upper}`` while leaving pre-formatted IDs and
unknown formats untouched.
"""

from __future__ import annotations

import re
from datetime import datetime
from typing import Any, Optional

_UUID_DASHED = re.compile(
    r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$"
)
_UUID_BARE = re.compile(r"^[0-9a-fA-F]{32}$")


def _resolve_year(valuation_date: Any) -> int:
    """Best-effort year extraction; today's year is the fallback."""
    try:
        if hasattr(valuation_date, "year"):
            year = int(valuation_date.year)
            if 2000 <= year <= 2100:
                return year
        if isinstance(valuation_date, str) and len(valuation_date) >= 4:
            year = int(valuation_date[:4])
            if 2000 <= year <= 2100:
                return year
    except (ValueError, TypeError):
        pass
    return datetime.now().year


def format_valuation_reference(
    valuation_id: Optional[str],
    valuation_date: Any = None,
) -> str:
    """Format a raw UUID into ``VAL-{year}-{first 4 hex upper}``.

    Behavior:
      - Empty / None input → empty string.
      - Already starts with ``VAL-`` → returned unchanged.
      - Looks like a UUID (dashed or bare) → reformatted.
      - Anything else → returned unchanged (assume legacy ID format).

    Defensive: never raises.
    """
    if not isinstance(valuation_id, str):
        return ""
    s = valuation_id.strip()
    if not s:
        return ""
    if s.upper().startswith("VAL-"):
        return s

    is_uuid = bool(_UUID_DASHED.match(s)) or bool(_UUID_BARE.match(s.replace("-", "")))
    if not is_uuid:
        return s

    year = _resolve_year(valuation_date)
    short = s.replace("-", "")[:4].upper()
    return f"VAL-{year}-{short}"
