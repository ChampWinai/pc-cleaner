"""Auto-update checker for PC Cleaner."""
import hashlib
import json
import logging
import subprocess
import tempfile
import requests
from datetime import datetime, timedelta
from pathlib import Path
import os

log = logging.getLogger(__name__)

CURRENT_VERSION = "1.1.3"  # Sync this with installer.iss line 6
GITHUB_REPO = "ChampWinai/pc-cleaner"
INSTALLER_ASSET = "PCCleaner-Setup.exe"
DOWNLOAD_PREFIX = f"https://github.com/{GITHUB_REPO}/releases/download/"
UPDATE_CHECK_FILE = Path(os.getenv('LOCALAPPDATA')) / 'PCCleaner' / '.last_update_check'


class UpdateChecker:
    """Check for new releases on GitHub."""

    @staticmethod
    def get_latest_release():
        """Fetch latest release info from GitHub API."""
        try:
            url = f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest"
            response = requests.get(url, timeout=5)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            log.warning(f"Failed to fetch latest release: {e}")
            return None

    @staticmethod
    def parse_version(version_str):
        """Parse version string (e.g., 'v1.0.0' -> (1, 0, 0))."""
        try:
            version_str = version_str.lstrip('v')
            # Remove any suffix like -beta, -alpha, -rc1
            version_str = version_str.split('-')[0]
            parts = version_str.split('.')
            return tuple(int(p) for p in parts[:3])
        except (ValueError, IndexError):
            return (0, 0, 0)

    @classmethod
    def is_newer_available(cls):
        """Check if a newer version is available."""
        release = cls.get_latest_release()
        if not release:
            return False
        
        latest_version = release.get('tag_name', '')
        latest_tuple = cls.parse_version(latest_version)
        current_tuple = cls.parse_version(CURRENT_VERSION)
        
        return latest_tuple > current_tuple

    @classmethod
    def get_update_info(cls):
        """Get update info if available."""
        release = cls.get_latest_release()
        if not release:
            return None
        
        latest_version = release.get('tag_name', '')
        latest_tuple = cls.parse_version(latest_version)
        current_tuple = cls.parse_version(CURRENT_VERSION)
        
        if latest_tuple <= current_tuple:
            return None
        
        asset = next((a for a in release.get('assets', []) if a.get('name') == INSTALLER_ASSET), {})
        return {
            'version': latest_version,
            'url': release.get('html_url', ''),
            'download_url': asset.get('browser_download_url', ''),
            'sha256': (asset.get('digest') or '').removeprefix('sha256:'),
            'size': asset.get('size', 0),
            'release_notes': release.get('body', ''),
            'published_at': release.get('published_at', ''),
        }

    @staticmethod
    def download_installer(info, on_progress=None):
        """Download the installer to %TEMP% and verify its SHA-256.

        Refuses anything not served from this repo's release URL, and refuses
        to proceed without a published digest -- we never run an unverified exe.
        Returns the local path; raises ValueError / requests errors on failure.
        """
        url, expected = info.get('download_url', ''), info.get('sha256', '')
        if not url.startswith(DOWNLOAD_PREFIX):
            raise ValueError("untrusted download URL")
        if len(expected) != 64:
            raise ValueError("release has no SHA-256 digest")
        dest = os.path.join(tempfile.gettempdir(), f"PCCleaner-Setup-{info['version'].lstrip('v')}.exe")
        digest = hashlib.sha256()
        with requests.get(url, stream=True, timeout=15) as r:
            r.raise_for_status()
            total = int(r.headers.get('content-length') or info.get('size') or 0)
            done = 0
            with open(dest, 'wb') as f:
                for chunk in r.iter_content(chunk_size=1 << 16):
                    f.write(chunk)
                    digest.update(chunk)
                    done += len(chunk)
                    if on_progress and total:
                        on_progress(done / total)
        if digest.hexdigest() != expected.lower():
            os.remove(dest)
            raise ValueError("checksum mismatch")
        return dest

    @staticmethod
    def run_installer(path):
        """Launch the verified installer silently; it closes and relaunches the app."""
        subprocess.Popen(
            [path, "/SILENT", "/CLOSEAPPLICATIONS", "/RESTARTAPPLICATIONS", "/NORESTART"],
            creationflags=getattr(subprocess, "DETACHED_PROCESS", 0),
        )

    @staticmethod
    def record_check_time():
        """Record when we last checked for updates."""
        try:
            UPDATE_CHECK_FILE.parent.mkdir(parents=True, exist_ok=True)
            with open(UPDATE_CHECK_FILE, 'w') as f:
                f.write(datetime.now().isoformat())
        except Exception as e:
            log.debug(f"Failed to record check time: {e}")

    @staticmethod
    def should_check_for_updates(interval_days=7):
        """Determine if enough time has passed to check again."""
        if not UPDATE_CHECK_FILE.exists():
            return True
        
        try:
            with open(UPDATE_CHECK_FILE, 'r') as f:
                last_check = datetime.fromisoformat(f.read())
            return datetime.now() - last_check > timedelta(days=interval_days)
        except Exception:
            return True

    @classmethod
    def check_and_notify(cls, interval_days=0.25):
        """
        Check for updates if interval has passed.
        Returns update info if available, None otherwise.
        """
        if not cls.should_check_for_updates(interval_days):
            return None
        
        cls.record_check_time()
        return cls.get_update_info()


__all__ = ['UpdateChecker', 'CURRENT_VERSION']
