import json
import os
import threading
from typing import List, Dict


_lock = threading.Lock()
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
TIMEOUTS_FILE = os.path.join(BASE_DIR, "timeouts.json")


def _ensure_file():
    if not os.path.exists(TIMEOUTS_FILE):
        try:
            with open(TIMEOUTS_FILE, "w", encoding="utf-8") as f:
                json.dump({"history": []}, f)
        except Exception:
            pass


def load_history() -> List[Dict]:
    _ensure_file()
    try:
        with _lock:
            with open(TIMEOUTS_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                return data.get("history", [])
    except Exception:
        return []


def save_history(history: List[Dict]):
    _ensure_file()
    # write atomically
    tmp = TIMEOUTS_FILE + ".tmp"
    try:
        with _lock:
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump({"history": history}, f,
                          ensure_ascii=False, indent=2)
            os.replace(tmp, TIMEOUTS_FILE)
    except Exception:
        try:
            if os.path.exists(tmp):
                os.remove(tmp)
        except Exception:
            pass


def append_entry(entry: Dict):
    hist = load_history()
    hist.append(entry)
    save_history(hist)
