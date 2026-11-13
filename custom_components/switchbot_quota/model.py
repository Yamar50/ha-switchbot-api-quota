"""Pure observation logic. An increase is evidence of replenishment, not its exact time."""

from datetime import datetime, timedelta
from email.utils import parsedate_to_datetime
import re

from .const import INTERVAL_SECONDS


def parse_remaining(status: int, headers) -> int:
    """Accept a real quota header, including exhausted HTTP 429 responses."""
    if status not in (200, 429):
        raise ValueError(f"HTTP {status}")
    # aiohttp uses a case-insensitive mapping; plain dict fixtures work too.
    value = next((str(v) for k, v in headers.items()
                  if k.lower() == "x-ratelimit-remaining"), "")
    if not re.fullmatch(r"[0-9]{1,9}", value):
        raise ValueError("Missing or invalid X-RateLimit-Remaining header")
    return int(value)


def next_attempt(snapshot: dict, now: datetime) -> datetime:
    """A persisted attempt also throttles reloads, failures and manual refreshes."""
    previous = snapshot.get("last_attempt_at")
    if not previous:
        return now
    return max(now, datetime.fromisoformat(previous) + timedelta(seconds=INTERVAL_SECONDS))


def observe(snapshot: dict, remaining: int, at: datetime, status: int, server_date: str) -> dict:
    result = dict(snapshot)
    previous = snapshot.get("remaining")
    if previous is not None and remaining > previous:
        result.update(
            last_increase_observed_at=at.isoformat(),
            increase_window_start=snapshot["observed_at"],
            remaining_before_increase=previous,
            remaining_after_increase=remaining,
            increases_observed=snapshot.get("increases_observed", 0) + 1,
        )
    result.update(remaining=remaining, observed_at=at.isoformat(),
                  http_status=status, last_error=None)
    try:
        result["server_date"] = parsedate_to_datetime(server_date).isoformat()
    except (ValueError, TypeError, OverflowError):
        result["server_date"] = None
    return result
