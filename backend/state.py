from datetime import datetime, timedelta
import os
from zoneinfo import ZoneInfo

import timeouts_store
from dotenv import load_dotenv

load_dotenv()

online_members = set()
last_spin = None
history = []


def _load_persistent():
    global history, last_spin
    try:
        history = timeouts_store.load_history()
        if history:
            # set last_spin from last entry if present
            try:
                last_entry = history[-1]
                parsed = datetime.fromisoformat(last_entry.get("time"))
                # ensure last_spin is timezone-aware (Europe/Paris) for consistent arithmetic
                if parsed.tzinfo is None:
                    parsed = parsed.replace(tzinfo=ZoneInfo("Europe/Paris"))
                last_spin = parsed
            except Exception:
                last_spin = None
    except Exception:
        history = []
        last_spin = None


_load_persistent()


def currtime() -> datetime:
    """Get the current datetime in Europe/Paris timezone."""
    return datetime.now(ZoneInfo("Europe/Paris"))


def is_happy_hour(now: datetime = None) -> bool:
    """Check if it is currently Happy Hour (Paris time).

    By default, Happy Hour is from 17:00 to 18:00 Paris time, but can be
    customized via environment variables START_HOUR_HAPPY_HOUR and
    END_HOUR_HAPPY_HOUR (24-hour format)."""
    try:
        if now is None:
            now = currtime()
        start_hour = int(os.getenv("START_HOUR_HAPPY_HOUR", 17))
        end_hour = int(os.getenv("END_HOUR_HAPPY_HOUR", 18))
        return start_hour <= now.hour < end_hour
    except Exception:
        return False


def seconds_until_next_spin():
    """Calculate the number of seconds until the next allowed spin.
    It starts by checking if we are in happy hour or not, to determine the cooldown period.
    Then, it calculates the time elapsed since the last spin and computes the remaining time
    until the next spin is allowed.
    If we are not in happy hour, the cooldown period is 1 hour (3600 seconds), otherwise it is 5 minutes (300 seconds).
    If the last spin happened before happy-hour started and the next spin is during happy-hour,
    consider the smallest cooldown between: the remaining time until happy-hour starts, and the happy-hour cooldown.
    """
    global last_spin
    if not last_spin:
        return 0

    now = currtime()
    in_happy_hour = is_happy_hour(now)
    cooldown = timedelta(minutes=5) if in_happy_hour else timedelta(hours=1)
    elapsed = now - last_spin
    remaining = cooldown - elapsed

    if remaining.total_seconds() <= 0:
        return 0

    if not in_happy_hour:
        # check if last spin was before happy-hour started
        start_hour = int(os.getenv("START_HOUR_HAPPY_HOUR", 17))
        happy_hour_start = now.replace(hour=start_hour, minute=0, second=0, microsecond=0)
        if last_spin < happy_hour_start < now:
            time_until_happy_hour = max(happy_hour_start - now, timedelta(minutes=5))
            remaining = min(remaining, time_until_happy_hour)
    return int(remaining.total_seconds())


def can_spin():
    global last_spin
    if not last_spin:
        return True

    limit = timedelta(minutes=5) if is_happy_hour() else timedelta(hours=1)
    # use currtime() (Europe/Paris, timezone-aware) to match last_spin which is stored timezone-aware
    return currtime() - last_spin >= limit


def register_spin(member_name, member_id=None, minutes=2):
    """Register a spin in memory and persistent store.

    member_id is optional (string). If provided, it's stored alongside the
    historical display name to allow resolving the latest name later while
    preserving the original recorded name.
    """
    global last_spin
    # use timezone-aware current time (Europe/Paris) so arithmetic with currtime() is consistent
    last_spin = currtime()
    ends_at = last_spin + timedelta(minutes=minutes)
    entry = {
        "member": member_name,
        "time": last_spin.isoformat(),
        "ends_at": ends_at.isoformat()
    }
    if member_id is not None:
        entry["member_id"] = str(member_id)
    history.append(entry)
    try:
        timeouts_store.append_entry(entry)
    except Exception:
        # best-effort: ignore persistence errors
        pass
