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


def happy_hour_start_end() -> tuple[int, int]:
    """Get the start and end hours of Happy Hour from environment variables.

    Returns a tuple (start_hour, end_hour). Defaults to (17, 18) if not set.
    """
    start_env = os.getenv("START_HOUR_HAPPY_HOUR", "17")
    end_env = os.getenv("END_HOUR_HAPPY_HOUR", "18")
    try:
        start_hour = int(start_env)
        end_hour = int(end_env)
        return start_hour, end_hour
    except ValueError:
        return 17, 18


def is_happy_hour(now: datetime = None) -> bool:
    """Check if it is currently Happy Hour (Paris time).

    By default, Happy Hour is from 17:00 to 18:00 Paris time, but can be
    customized via environment variables START_HOUR_HAPPY_HOUR and
    END_HOUR_HAPPY_HOUR (24-hour format)."""
    try:
        if now is None:
            now = currtime()
        start_hour, end_hour = happy_hour_start_end()
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
    If we are in happy hour and the last spin is after the last "cooldown" minutes, we need to wait the standard cooldown.
    """
    global last_spin
    if not last_spin:
        return 0

    now = currtime()
    in_happy_hour = is_happy_hour(now)
    happy_hour_cooldown = timedelta(minutes=5)
    standard_cooldown = timedelta(hours=1)
    cooldown = happy_hour_cooldown if in_happy_hour else standard_cooldown
    elapsed = now - last_spin
    remaining = cooldown - elapsed

    if remaining.total_seconds() <= 0:
        return 0

    # logic for transitions around happy hours
    start_hour, end_hour = happy_hour_start_end()
    if not in_happy_hour:
        # check if next spin would be in happy hour
        happy_hour_start = now.replace(hour=start_hour, minute=0, second=0, microsecond=0)
        if last_spin < happy_hour_start <= now + remaining:
            time_until_happy_hour = happy_hour_start - now
            # if the time until happy hour is more than the happy hour cooldown, use the time until happy hour
            # otherwise, add some extra time so that would only have waited the happy hour cooldown in total
            if time_until_happy_hour > happy_hour_cooldown:
                remaining = time_until_happy_hour
            else:
                remaining = happy_hour_cooldown - time_until_happy_hour
    if in_happy_hour:
        # when in happy hour, if the next spin is after the happy hour will end,
        # we need to wait the standard cooldown (minus elapsed time)
        happy_hour_end = now.replace(hour=end_hour, minute=0, second=0, microsecond=0)
        if last_spin + happy_hour_cooldown > happy_hour_end:
            remaining = standard_cooldown - elapsed

    return int(remaining.total_seconds())


def can_spin():
    """Check if a new spin can be performed based on the cooldown period."""
    return seconds_until_next_spin() == 0


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
