"""Updater safety: only verified installers from this repo's releases are run."""
import hashlib
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import update_checker
from update_checker import UpdateChecker, DOWNLOAD_PREFIX

DATA = b"installer-bytes"
GOOD = hashlib.sha256(DATA).hexdigest()


class FakeResp:
    headers = {"content-length": str(len(DATA))}
    def __enter__(self): return self
    def __exit__(self, *a): return False
    def raise_for_status(self): pass
    def iter_content(self, chunk_size): yield DATA


def info(**kw):
    d = {"version": "v9.9.9", "download_url": DOWNLOAD_PREFIX + "v9.9.9/PCCleaner-Setup.exe",
         "sha256": GOOD, "size": len(DATA)}
    d.update(kw)
    return d


@pytest.fixture(autouse=True)
def fake_net(tmp_path, monkeypatch):
    monkeypatch.setattr(update_checker.requests, "get", lambda *a, **k: FakeResp())
    monkeypatch.setattr(update_checker.tempfile, "gettempdir", lambda: str(tmp_path))


def test_picks_installer_asset_not_first_asset(monkeypatch):
    monkeypatch.setattr(UpdateChecker, "get_latest_release", staticmethod(lambda: {
        "tag_name": "v9.9.9",
        "assets": [{"name": "PCCleaner-portable.zip", "browser_download_url": "zip"},
                   {"name": "PCCleaner-Setup.exe", "browser_download_url": "exe",
                    "digest": "sha256:abc", "size": 5}]}))
    i = UpdateChecker.get_update_info()
    assert i["download_url"] == "exe" and i["sha256"] == "abc"


def test_download_verifies_and_reports_progress():
    seen = []
    path = UpdateChecker.download_installer(info(), seen.append)
    assert open(path, "rb").read() == DATA and seen[-1] == 1.0


def test_rejects_foreign_url():
    with pytest.raises(ValueError):
        UpdateChecker.download_installer(info(download_url="https://evil.example/x.exe"))


def test_rejects_missing_digest():
    with pytest.raises(ValueError):
        UpdateChecker.download_installer(info(sha256=""))


def test_checksum_mismatch_deletes_file(tmp_path):
    with pytest.raises(ValueError):
        UpdateChecker.download_installer(info(sha256="0" * 64))
    assert not list(tmp_path.glob("PCCleaner-Setup-*.exe"))
