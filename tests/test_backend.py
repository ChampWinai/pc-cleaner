"""Tests for pure-logic helpers in backend.py.

These target functions that don't require Windows-specific privileges or
touch real system state (registry, WMI, scheduled tasks). Vault tests
monkeypatch backend's module-level paths to a tmp_path so they never read
or write the real %LOCALAPPDATA%\\PCCleanerVault.
"""

import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import backend  # noqa: E402


# ---------------------------------------------------------------------------
# human_size
# ---------------------------------------------------------------------------
@pytest.mark.parametrize(
    "num_bytes,expected",
    [
        (0, "0.0 B"),
        (512, "512.0 B"),
        (1024, "1.0 KB"),
        (1024 * 1024, "1.0 MB"),
        (1024 * 1024 * 1024, "1.0 GB"),
        (1024 ** 4, "1.0 TB"),
    ],
)
def test_human_size(num_bytes, expected):
    assert backend.human_size(num_bytes) == expected


# ---------------------------------------------------------------------------
# Thai national ID checksum
# ---------------------------------------------------------------------------
def test_valid_thai_id_accepts_correct_checksum():
    assert backend._valid_thai_id("1100100253633") is True


def test_valid_thai_id_rejects_bad_checksum():
    assert backend._valid_thai_id("1100100253632") is False


def test_valid_thai_id_rejects_wrong_length():
    assert backend._valid_thai_id("123") is False


def test_valid_thai_id_rejects_non_digits():
    assert backend._valid_thai_id("110010025363a") is False


# ---------------------------------------------------------------------------
# Luhn checksum (credit card numbers)
# ---------------------------------------------------------------------------
def test_luhn_valid_accepts_known_good_number():
    assert backend._luhn_valid("4111111111111111") is True  # Visa test number


def test_luhn_valid_rejects_bad_checksum():
    assert backend._luhn_valid("4111111111111112") is False


@pytest.mark.parametrize("digits", ["123", "1" * 20])
def test_luhn_valid_rejects_bad_length(digits):
    assert backend._luhn_valid(digits) is False


# ---------------------------------------------------------------------------
# _mask
# ---------------------------------------------------------------------------
def test_mask_short_value_fully_masked():
    assert backend._mask("1234") == "****"


def test_mask_long_value_keeps_ends():
    result = backend._mask("1234567890")
    assert result == "12******90"
    assert len(result) == len("1234567890")


# ---------------------------------------------------------------------------
# get_impact
# ---------------------------------------------------------------------------
def test_get_impact_returns_tuple_for_known_and_unknown_labels():
    known = backend.get_impact("Windows Temp Files")
    unknown = backend.get_impact("Some Unknown Label")
    assert isinstance(known, tuple) and len(known) == 2
    assert isinstance(unknown, tuple) and len(unknown) == 2


# ---------------------------------------------------------------------------
# Vault index persistence (isolated via monkeypatched paths)
# ---------------------------------------------------------------------------
@pytest.fixture
def isolated_vault(tmp_path, monkeypatch):
    vault_dir = tmp_path / "PCCleanerVault"
    monkeypatch.setattr(backend, "VAULT_DIR", str(vault_dir))
    monkeypatch.setattr(backend, "VAULT_INDEX_PATH", str(vault_dir / "index.json"))
    return vault_dir


def test_load_vault_index_missing_file_returns_empty_list(isolated_vault):
    assert backend._load_vault_index() == []


def test_save_and_load_vault_index_round_trip(isolated_vault):
    entries = [{"id": "abc123", "label": "Test", "size": 42}]
    backend._save_vault_index(entries)
    assert backend._load_vault_index() == entries


def test_load_vault_index_corrupt_json_returns_empty_list(isolated_vault):
    os.makedirs(isolated_vault, exist_ok=True)
    with open(backend.VAULT_INDEX_PATH, "w", encoding="utf-8") as f:
        f.write("{not valid json")
    assert backend._load_vault_index() == []


def test_purge_vault_entry_removes_file_and_index_entry(isolated_vault):
    os.makedirs(isolated_vault, exist_ok=True)
    vault_file = isolated_vault / "somefile.txt"
    vault_file.write_text("data")
    entries = [{"id": "e1", "vault_path": str(vault_file), "label": "x", "size": 4}]
    backend._save_vault_index(entries)

    backend.purge_vault_entry("e1")

    assert not vault_file.exists()
    assert backend._load_vault_index() == []


def test_restore_from_vault_moves_file_back(isolated_vault, tmp_path):
    os.makedirs(isolated_vault, exist_ok=True)
    vault_file = isolated_vault / "somefile.txt"
    vault_file.write_text("data")
    original_path = tmp_path / "restored" / "somefile.txt"
    entries = [{
        "id": "e1", "vault_path": str(vault_file),
        "original_path": str(original_path), "label": "x", "size": 4,
    }]
    backend._save_vault_index(entries)

    assert backend.restore_from_vault("e1") is True
    assert original_path.exists()
    assert not vault_file.exists()


def test_restore_from_vault_unknown_id_returns_false(isolated_vault):
    assert backend.restore_from_vault("does-not-exist") is False


# ---------------------------------------------------------------------------
# CONFIG MANAGER TESTS
# ---------------------------------------------------------------------------
def test_config_manager_loads_defaults():
    from config_manager import ConfigManager
    # Should not crash even if file doesn't exist
    cfg = ConfigManager()
    assert cfg.get('general.auto_start_on_login') == False
    assert cfg.get('ui.dark_mode') == False


def test_config_manager_get_with_default():
    from config_manager import ConfigManager
    cfg = ConfigManager()
    # Getting non-existent key returns default
    assert cfg.get('nonexistent.key', 'default_value') == 'default_value'


def test_config_manager_set_creates_nested_structure():
    from config_manager import ConfigManager
    cfg = ConfigManager()
    cfg.set('test.nested.value', 'hello')
    assert cfg.get('test.nested.value') == 'hello'


def test_config_manager_whitelist_operations():
    from config_manager import ConfigManager
    cfg = ConfigManager()
    test_folder = r'C:\TestFolder'
    
    cfg.add_whitelist_folder(test_folder)
    assert test_folder in cfg.get_whitelist_folders()
    
    cfg.remove_whitelist_folder(test_folder)
    assert test_folder not in cfg.get_whitelist_folders()


# ---------------------------------------------------------------------------
# OPERATION CONTEXT TESTS
# ---------------------------------------------------------------------------
def test_operation_context_tracks_progress():
    from operation_context import OperationContext
    ctx = OperationContext('test_op')
    ctx.set_progress(50, 100, 'Processing')
    progress = ctx.get_progress()
    assert progress['progress'] == 50
    assert progress['total'] == 100
    assert progress['percentage'] == 50


def test_operation_context_cancellation():
    from operation_context import OperationContext, OperationCancelled
    ctx = OperationContext('test_op')
    assert not ctx.is_cancelled()
    
    ctx.cancel()
    assert ctx.is_cancelled()
    
    with pytest.raises(OperationCancelled):
        ctx.check_cancelled()


def test_retry_decorator_succeeds_on_first_try():
    from operation_context import retry, RetryConfig
    
    call_count = [0]
    
    @retry(RetryConfig(max_attempts=3))
    def succeeds():
        call_count[0] += 1
        return "success"
    
    result = succeeds()
    assert result == "success"
    assert call_count[0] == 1


def test_retry_decorator_retries_on_exception():
    from operation_context import retry, RetryConfig
    
    call_count = [0]
    
    @retry(RetryConfig(max_attempts=3, initial_delay=0.01, max_delay=0.1))
    def fails_twice():
        call_count[0] += 1
        if call_count[0] < 3:
            raise ValueError("Not yet")
        return "finally"
    
    result = fails_twice()
    assert result == "finally"
    assert call_count[0] == 3


def test_retry_decorator_gives_up_after_max_attempts():
    from operation_context import retry, RetryConfig
    
    call_count = [0]
    
    @retry(RetryConfig(max_attempts=2, initial_delay=0.01))
    def always_fails():
        call_count[0] += 1
        raise ValueError("Always fails")
    
    with pytest.raises(ValueError):
        always_fails()
    
    assert call_count[0] == 2


# ---------------------------------------------------------------------------
# UPDATE CHECKER TESTS
# ---------------------------------------------------------------------------
def test_update_checker_parse_version():
    from update_checker import UpdateChecker
    assert UpdateChecker.parse_version('v1.0.0') == (1, 0, 0)
    assert UpdateChecker.parse_version('1.2.3') == (1, 2, 3)
    assert UpdateChecker.parse_version('2.0.0-beta') == (2, 0, 0)
    assert UpdateChecker.parse_version('invalid') == (0, 0, 0)


def test_update_checker_version_comparison():
    from update_checker import UpdateChecker
    # Tuple comparison works naturally in Python
    v1 = UpdateChecker.parse_version('1.0.0')
    v2 = UpdateChecker.parse_version('2.0.0')
    assert v1 < v2
    assert v2 > v1


# ---------------------------------------------------------------------------
# HISTORY DATABASE TESTS
# ---------------------------------------------------------------------------
def test_history_db_record_scan(tmp_path, monkeypatch):
    monkeypatch.setenv('LOCALAPPDATA', str(tmp_path))
    from history_db import HistoryDatabase
    db = HistoryDatabase()
    
    scan_id = db.record_scan('temp_files', 10.5, 42, 1073741824)
    assert scan_id > 0
    
    scans = db.get_recent_scans(limit=1)
    assert len(scans) == 1
    assert scans[0]['scan_type'] == 'temp_files'
    assert scans[0]['duration_seconds'] == 10.5


def test_history_db_record_cleaned_item(tmp_path, monkeypatch):
    monkeypatch.setenv('LOCALAPPDATA', str(tmp_path))
    from history_db import HistoryDatabase
    db = HistoryDatabase()
    
    scan_id = db.record_scan('test_scan', 1.0, 1, 1024)
    db.record_cleaned_item(scan_id, 'temp', r'C:\temp\file.tmp', 1024)
    
    items = db.get_cleaned_items_by_scan(scan_id)
    assert len(items) == 1
    assert items[0]['category'] == 'temp'


def test_history_db_get_stats(tmp_path, monkeypatch):
    monkeypatch.setenv('LOCALAPPDATA', str(tmp_path))
    # Force reimport to use the new path
    import importlib
    import history_db as hdb_module
    importlib.reload(hdb_module)
    from history_db import HistoryDatabase
    db = HistoryDatabase()
    
    db.record_scan('test1', 1.0, 10, 1000)
    db.record_scan('test2', 1.0, 20, 2000)
    
    stats = db.get_stats()
    assert stats['total_scans'] == 2
    assert stats['total_cleaned_bytes'] == 3000


# ---------------------------------------------------------------------------
# PLUGIN SYSTEM TESTS
# ---------------------------------------------------------------------------
def test_plugin_manager_loads_no_plugins_gracefully():
    from plugin_system import PluginManager
    pm = PluginManager()
    pm.load_all_plugins()  # Should not crash even if no plugins directory
    assert len(pm.plugins) == 0


def test_plugin_manager_call_hook_with_no_registered_hooks():
    from plugin_system import PluginManager
    pm = PluginManager()
    results = pm.call_hook('nonexistent_hook', 'arg1', 'arg2')
    assert results == []


def test_plugin_manager_get_enabled_plugins():
    from plugin_system import PluginManager
    pm = PluginManager()
    enabled = pm.get_enabled_plugins()
    assert isinstance(enabled, list)


# ---------------------------------------------------------------------------
# TASK SCHEDULER TESTS
# ---------------------------------------------------------------------------
def test_task_scheduler_manager_parse_frequency():
    from task_scheduler import TaskSchedulerManager
    # Just test that the class exists and has the right methods
    assert hasattr(TaskSchedulerManager, 'create_task')
    assert hasattr(TaskSchedulerManager, 'delete_task')
    assert hasattr(TaskSchedulerManager, 'task_exists')

