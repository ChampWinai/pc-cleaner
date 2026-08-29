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
