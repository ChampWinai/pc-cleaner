"""Tests for Auto Clean, batched vault writes and windows_optimizer.

Everything touching schtasks / winreg / the real vault is mocked or
redirected to tmp_path.
"""

import os
import subprocess
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import backend
import windows_optimizer


@pytest.fixture
def sandbox(tmp_path, monkeypatch):
    vault = tmp_path / "vault"
    monkeypatch.setattr(backend, "VAULT_DIR", str(vault))
    monkeypatch.setattr(backend, "VAULT_INDEX_PATH", str(vault / "index.json"))
    monkeypatch.setattr(backend, "AUTO_CLEAN_SETTINGS_PATH", str(tmp_path / "settings.json"))
    monkeypatch.setattr(backend, "AUTO_CLEAN_LOG_PATH", str(tmp_path / "log.json"))
    return tmp_path


def test_run_auto_clean_only_touches_safe_items(sandbox, monkeypatch):
    found = [
        {"label": "a", "path": "pa", "size": 10, "risk": "safe", "note": ""},
        {"label": "b", "path": "pb", "size": 20, "risk": "medium", "note": ""},
        {"label": "c", "path": "pc", "size": 30, "risk": "high", "note": ""},
    ]
    cleaned = []
    monkeypatch.setattr(backend, "scan", lambda deep=False: found)
    monkeypatch.setattr(backend, "clean_items",
                        lambda items: (cleaned.extend(items) or 10, [], "batch"))
    entry = backend.run_auto_clean()
    assert [i["label"] for i in cleaned] == ["a"]
    assert entry["items_cleaned"] == 1 and entry["freed"] == 10
    assert backend.auto_clean_last_run()["freed"] == 10


def test_run_auto_clean_nothing_safe_skips_clean(sandbox, monkeypatch):
    monkeypatch.setattr(backend, "scan", lambda deep=False: [
        {"label": "b", "path": "pb", "size": 20, "risk": "high", "note": ""}])
    monkeypatch.setattr(backend, "clean_items", lambda items: pytest.fail("must not clean"))
    assert backend.run_auto_clean()["items_cleaned"] == 0


def test_clean_items_writes_vault_index_once(sandbox, monkeypatch):
    target = sandbox / "cache"
    target.mkdir()
    for i in range(5):
        (target / f"f{i}.tmp").write_text("x" * 10)
    saves = []
    real_save = backend._save_vault_index
    monkeypatch.setattr(backend, "_save_vault_index",
                        lambda e: (saves.append(len(e)), real_save(e))[1])
    freed, errors, _ = backend.clean_items([{"label": "t", "path": str(target)}])
    assert errors == [] and freed == 50
    assert saves == [5]
    assert os.listdir(target) == []


def test_auto_clean_enable_clamps_interval_and_saves(sandbox, monkeypatch):
    calls = []
    monkeypatch.setattr(subprocess, "run", lambda cmd, **kw: calls.append(cmd))
    ok, _ = backend.auto_clean_enable(interval_hours=99, deep=True)
    assert ok
    cmd = calls[0]
    assert cmd[cmd.index("/mo") + 1] == "24"
    assert "--deep" in cmd[cmd.index("/tr") + 1]
    assert backend.auto_clean_settings() == {"enabled": True, "interval_hours": 24, "deep": True}


def test_auto_clean_enable_failure_leaves_settings_untouched(sandbox, monkeypatch):
    def boom(cmd, **kw):
        raise subprocess.CalledProcessError(1, cmd)
    monkeypatch.setattr(subprocess, "run", boom)
    ok, msg = backend.auto_clean_enable()
    assert not ok and msg
    assert backend.auto_clean_settings()["enabled"] is False


def test_auto_clean_disable_marks_disabled(sandbox, monkeypatch):
    monkeypatch.setattr(subprocess, "run", lambda cmd, **kw: None)
    backend._save_json(backend.AUTO_CLEAN_SETTINGS_PATH,
                       {"enabled": True, "interval_hours": 2, "deep": False})
    assert backend.auto_clean_disable()
    assert backend.auto_clean_settings()["enabled"] is False


def test_network_flush_does_not_drop_connection(monkeypatch):
    cmds = []
    monkeypatch.setattr(subprocess, "run", lambda cmd, **kw: (cmds.append(cmd),
                        subprocess.CompletedProcess(cmd, 0, "ok", ""))[1])
    backend.network_flush()
    assert not any("release" in c or "renew" in c for c in cmds)


def test_disable_telemetry_reports_service_failure(monkeypatch):
    class Key:
        def __enter__(self): return self
        def __exit__(self, *a): return False
    monkeypatch.setattr(windows_optimizer.winreg, "CreateKey", lambda *a: Key())
    monkeypatch.setattr(windows_optimizer.winreg, "SetValueEx", lambda *a: None)
    monkeypatch.setattr(subprocess, "run",
                        lambda cmd, **kw: subprocess.CompletedProcess(cmd, 5, "", ""))
    res = windows_optimizer.disable_telemetry()
    assert res[0]["success"] and not res[1]["success"]


def test_clean_registry_deletes_all_values(monkeypatch):
    values = ["a", "b", "c"]
    deleted = []

    class Key:
        def __enter__(self): return self
        def __exit__(self, *a): return False
    w = windows_optimizer.winreg
    monkeypatch.setattr(w, "OpenKey", lambda *a: Key())
    def enum(key, i):
        if i >= len(values):
            raise OSError
        return (values[i], None, 0)
    monkeypatch.setattr(w, "EnumValue", enum)
    monkeypatch.setattr(w, "DeleteValue", lambda key, n: deleted.append(n))
    res = windows_optimizer.clean_registry()
    assert res["success"] and deleted == values


def test_clean_registry_missing_key_reports_failure(monkeypatch):
    def nokey(*a):
        raise FileNotFoundError("nope")
    monkeypatch.setattr(windows_optimizer.winreg, "OpenKey", nokey)
    assert windows_optimizer.clean_registry()["success"] is False
