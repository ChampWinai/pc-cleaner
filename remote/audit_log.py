"""Local, human-readable log of every remote-assistance session on this
device -- who connected, when, and for how long. Visible to the device
owner from the same UI panel as the Unattended Access toggle, not hidden.
"""

import json
import os
import time


def _log_path():
    return os.path.join(os.path.expanduser("~"), ".pc_cleaner_remote_audit.jsonl")


def log_event(event: dict):
    entry = {"time": time.time(), **event}
    with open(_log_path(), "a", encoding="utf-8") as f:
        f.write(json.dumps(entry) + "\n")


def get_events(limit=50):
    path = _log_path()
    if not os.path.exists(path):
        return []
    with open(path, "r", encoding="utf-8") as f:
        lines = f.readlines()[-limit:]
    events = []
    for line in lines:
        try:
            events.append(json.loads(line))
        except Exception:
            pass
    events.reverse()
    return events
