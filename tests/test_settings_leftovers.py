"""Settings validation, leftover finder safety, release-notes cleanup."""

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import backend
import system_tools
from update_checker import UpdateChecker


def test_settings_are_clamped(tmp_path, monkeypatch):
    monkeypatch.setattr(backend, "APP_SETTINGS_PATH", str(tmp_path / "a.json"))
    assert backend.app_settings() == backend.APP_SETTINGS_DEFAULT
    s = backend.save_app_settings({"close_to_tray": 0, "vault_retention_days": 999, "junk_notify_gb": -5})
    assert s == {"close_to_tray": False, "vault_retention_days": 90, "junk_notify_gb": 0.0}
    assert backend.app_settings() == s


def test_junk_notice_off_at_zero(tmp_path, monkeypatch):
    monkeypatch.setattr(backend, "APP_SETTINGS_PATH", str(tmp_path / "a.json"))
    monkeypatch.setattr(backend, "AUTO_CLEAN_SETTINGS_PATH", str(tmp_path / "s.json"))
    backend.save_app_settings({"junk_notify_gb": 0})
    assert backend.should_notify_junk({"review_bytes": 10 ** 12}) is False


def test_leftovers_only_for_gone_apps_and_inside_roots(tmp_path, monkeypatch):
    appdata, pf = tmp_path / "AppData", tmp_path / "PF"
    (appdata / "FooBar").mkdir(parents=True)
    (appdata / "FooBar" / "x.dat").write_bytes(b"12345")
    (pf / "Acme" / "FooBar").mkdir(parents=True)
    (appdata / "StillHere").mkdir()
    monkeypatch.setattr(system_tools, "UNINSTALLED_LOG", str(tmp_path / "u.json"))
    monkeypatch.setattr(system_tools, "_leftover_roots", lambda: [str(appdata), str(pf)])
    installed = [{"name": "Still Here"}]
    monkeypatch.setattr(system_tools, "list_installed_apps", lambda: installed)
    (tmp_path / "u.json").write_text(json.dumps([
        {"name": "FooBar 2.1 (x64)", "publisher": "Acme", "install_location": str(tmp_path)},  # root-level loc: refused
        {"name": "Still Here", "publisher": "", "install_location": ""},
        {"name": "Ghost", "publisher": "", "install_location": ""},
    ]), encoding="utf-8")

    found = system_tools.find_leftovers()
    paths = sorted(f["path"] for f in found)
    assert paths == sorted([str(appdata / "FooBar"), str(pf / "Acme" / "FooBar")])
    assert next(f for f in found if f["path"] == str(appdata / "FooBar"))["size"] == 5
    # "Ghost" had nothing left, so it drops off; the still-installed app stays tracked.
    names = [e["name"] for e in json.loads((tmp_path / "u.json").read_text(encoding="utf-8"))]
    assert names == ["FooBar 2.1 (x64)", "Still Here"]


def test_vault_leftover_rejects_paths_not_reported(monkeypatch):
    from api import Api
    monkeypatch.setattr(backend, "find_leftovers", lambda: [{"app": "A", "path": r"C:\ok", "size": 1}])
    moved = []
    monkeypatch.setattr(backend, "move_to_vault", lambda p, b, l: moved.append(p))
    assert Api().vault_leftover(r"C:\Windows\System32") == {"success": False}
    assert Api().vault_leftover(r"C:\ok") == {"success": True}
    assert moved == [r"C:\ok"]


def test_clean_notes():
    body = "## What's Changed\n* fix: tray close\n\nCo-Authored-By: x\n**Full Changelog**: https://x"
    assert UpdateChecker.clean_notes(body) == "fix: tray close"
    assert UpdateChecker.clean_notes("a" * 700).endswith("…")
