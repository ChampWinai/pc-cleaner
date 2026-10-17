"""Reliability/safety: vault locking, atomic index writes, single instance,
and trust-boundary checks on commands that originate in the UI."""

import json
import os
import subprocess
import sys
import textwrap
import threading

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import backend
import windows_optimizer

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


@pytest.fixture
def vault(tmp_path, monkeypatch):
    monkeypatch.setattr(backend, "VAULT_DIR", str(tmp_path))
    monkeypatch.setattr(backend, "VAULT_INDEX_PATH", str(tmp_path / "index.json"))
    return tmp_path


def test_concurrent_threads_do_not_lose_entries(vault):
    def add(n):
        for i in range(25):
            with backend._vault_locked():
                e = backend._load_vault_index()
                e.append({"id": f"{n}-{i}"})
                backend._save_vault_index(e)
    threads = [threading.Thread(target=add, args=(n,)) for n in range(4)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert len(backend._load_vault_index()) == 100


def test_lock_blocks_other_process(vault):
    script = textwrap.dedent(f"""
        import sys; sys.path.insert(0, {ROOT!r})
        import backend
        backend.VAULT_DIR = {str(vault)!r}
        backend.VAULT_INDEX_PATH = {str(vault / "index.json")!r}
        try:
            with backend._vault_locked(timeout=0.5):
                print("got")
        except TimeoutError:
            print("blocked")
    """)
    with backend._vault_locked():
        out = subprocess.run([sys.executable, "-c", script], capture_output=True, text=True, timeout=30)
    assert out.stdout.strip() == "blocked"
    out = subprocess.run([sys.executable, "-c", script], capture_output=True, text=True, timeout=30)
    assert out.stdout.strip() == "got"


def test_lock_is_reentrant(vault):
    with backend._vault_locked():
        with backend._vault_locked():
            backend._save_vault_index([{"id": "x"}])
    assert backend._load_vault_index() == [{"id": "x"}]


def test_corrupt_index_is_preserved_not_overwritten(vault):
    (vault / "index.json").write_text("{not json", encoding="utf-8")
    assert backend._load_vault_index() == []
    backups = list(vault.glob("index.json.corrupt-*"))
    assert len(backups) == 1 and backups[0].read_text(encoding="utf-8") == "{not json"


def test_save_is_atomic_on_failure(vault, monkeypatch):
    backend._save_vault_index([{"id": "keep"}])
    monkeypatch.setattr(backend.json, "dump", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("boom")))
    with pytest.raises(RuntimeError):
        backend._save_vault_index([{"id": "new"}])
    assert json.loads((vault / "index.json").read_text(encoding="utf-8")) == [{"id": "keep"}]


def test_single_instance_mutex():
    name = f"PCCleanerTest_{os.getpid()}"
    first = backend.acquire_single_instance(name)
    assert first
    assert backend.acquire_single_instance(name) is None


def test_remove_bloatware_rejects_unknown_package(monkeypatch):
    calls = []
    monkeypatch.setattr(windows_optimizer, "_ps", lambda cmd, timeout=60: calls.append(cmd))
    res = windows_optimizer.remove_bloatware(["x'; Remove-Item C:/ -Recurse; '"])
    assert res[0]["success"] is False and calls == []


def test_list_bloatware_only_installed(monkeypatch):
    monkeypatch.setattr(windows_optimizer, "_ps", lambda cmd, timeout=60:
                        subprocess.CompletedProcess(cmd, 0, "Microsoft.WindowsCamera\nSomething.Else\n", ""))
    got = windows_optimizer.list_bloatware()
    assert [g["package"] for g in got] == ["Microsoft.WindowsCamera"]
    assert got[0]["checked"] is False


def test_uninstall_app_runs_registry_command_without_shell(monkeypatch):
    import system_tools
    monkeypatch.setattr(system_tools, "list_installed_apps", lambda: [
        {"id": "Foo", "uninstall_string": r'"C:\Foo\unins.exe"', "quiet_uninstall_string": ""}])
    launched = []
    monkeypatch.setattr(system_tools.subprocess, "Popen", lambda cmd, **kw: launched.append((cmd, kw)))
    assert backend.uninstall_app("Nope") is False
    assert backend.uninstall_app("Foo") is True
    assert launched == [(r'"C:\Foo\unins.exe"', {})]
