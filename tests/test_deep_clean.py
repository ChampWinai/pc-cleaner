"""Deeper cleaning: per-profile browser caches, clean progress, history."""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import backend


def test_browser_caches_cover_every_profile(tmp_path):
    base = tmp_path / "Google" / "Chrome" / "User Data"
    for prof in ("Default", "Profile 1", "Profile 2", "System Profile", "Crashpad"):
        (base / prof / "Cache").mkdir(parents=True)
    got = dict(backend._browser_profile_caches({"LOCALAPPDATA": str(tmp_path)}))
    assert got["Chrome Cache"].endswith(os.path.join("Default", "Cache"))
    assert "Chrome Cache (Profile 1)" in got and "Chrome Cache (Profile 2)" in got
    assert not any("System Profile" in k or "Crashpad" in k for k in got)
    assert backend.get_impact("Chrome Cache – GPUCache (Profile 1)")[0] == "low"


def test_clean_progress_counts_every_file(tmp_path, monkeypatch):
    monkeypatch.setattr(backend, "VAULT_DIR", str(tmp_path / "vault"))
    monkeypatch.setattr(backend, "VAULT_INDEX_PATH", str(tmp_path / "vault" / "index.json"))
    src = tmp_path / "c"
    src.mkdir()
    for i in range(7):
        (src / f"{i}.tmp").write_text("x")
    backend.clean_items([{"label": "t", "path": str(src)}])
    assert backend.clean_progress == {"done": 7, "total": 7}


def test_record_clean_history(monkeypatch):
    rows, items = [], []
    monkeypatch.setattr(backend.history_db, "record_scan", lambda *a: rows.append(a) or 42)
    monkeypatch.setattr(backend.history_db, "record_cleaned_item", lambda *a: items.append(a))
    backend.record_clean_history("manual", [{"label": "A", "path": "p", "size": 5}, {"label": "B", "path": "q"}], 9)
    assert rows == [("manual", 0, 2, 9)]
    assert items == [(42, "A", "p", 5), (42, "B", "q", 0)]


def test_junk_notice_throttled_to_once_a_day(tmp_path, monkeypatch):
    monkeypatch.setattr(backend, "AUTO_CLEAN_SETTINGS_PATH", str(tmp_path / "s.json"))
    monkeypatch.setattr(backend, "APP_SETTINGS_PATH", str(tmp_path / "a.json"))
    big = {"review_bytes": 2 * 1024 ** 3}
    assert backend.should_notify_junk({"review_bytes": 10}) is False
    assert backend.should_notify_junk(big) is True
    assert backend.should_notify_junk(big) is False


def test_run_auto_clean_reports_reviewable_junk(tmp_path, monkeypatch):
    monkeypatch.setattr(backend, "AUTO_CLEAN_LOG_PATH", str(tmp_path / "l.json"))
    monkeypatch.setattr(backend, "record_clean_history", lambda *a: None)
    monkeypatch.setattr(backend, "scan", lambda deep=False: [
        {"label": "a", "path": "a", "size": 5, "risk": "safe"},
        {"label": "b", "path": "b", "size": 7, "risk": "low"}])
    monkeypatch.setattr(backend, "clean_items", lambda items: (5, [], "x"))
    assert backend.run_auto_clean()["review_bytes"] == 7
