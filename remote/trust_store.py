"""Persisted "Unattended Access" opt-in.

This file only exists if the device owner explicitly turned Unattended
Access on (via a confirm dialog in the UI). Its presence means: connections
using the stored code skip the per-session Allow/Deny prompt. Everything
else (visible overlay, kill switch, audit log) still applies -- this is not
a silent/hidden mode, just a pre-approved one.
"""

import json
import os


def _path():
    return os.path.join(os.path.expanduser("~"), ".pc_cleaner_remote_trust.json")


def load():
    path = _path()
    if not os.path.exists(path):
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


def save(data: dict):
    with open(_path(), "w", encoding="utf-8") as f:
        json.dump(data, f)


def is_enabled():
    data = load()
    return bool(data and data.get("enabled"))


def clear():
    path = _path()
    if os.path.exists(path):
        os.remove(path)
