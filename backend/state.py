from datetime import datetime, timedelta
import os

import timeouts_store


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
                last_spin = datetime.fromisoformat(last_entry.get("time"))
            except Exception:
                last_spin = None
    except Exception:
        history = []
        last_spin = None


_load_persistent()


def can_spin():
    global last_spin
    if not last_spin:
        return True
    return datetime.utcnow() - last_spin >= timedelta(hours=1)


def register_spin(member_name, minutes=2):
    global last_spin
    last_spin = datetime.utcnow()
    ends_at = last_spin + timedelta(minutes=minutes)
    entry = {
        "member": member_name,
        "time": last_spin.isoformat(),
        "ends_at": ends_at.isoformat()
    }
    history.append(entry)
    try:
        timeouts_store.append_entry(entry)
    except Exception:
        # best-effort: ignore persistence errors
        pass
