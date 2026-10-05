"""Auto-update checker for PC Cleaner."""
import json
import logging
import requests
from datetime import datetime, timedelta
from pathlib import Path
import os

log = logging.getLogger(__name__)

CURRENT_VERSION = "1.1.0"  # Sync this with installer.iss line 6
GITHUB_REPO = "ChampWinai/pc-cleaner"
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
        
        return {
            'version': latest_version,
            'url': release.get('html_url', ''),
            'download_url': release.get('assets', [{}])[0].get('browser_download_url', '') if release.get('assets') else '',
            'release_notes': release.get('body', ''),
            'published_at': release.get('published_at', ''),
        }

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
    def check_and_notify(cls, interval_days=7):
        """
        Check for updates if interval has passed.
        Returns update info if available, None otherwise.
        """
        if not cls.should_check_for_updates(interval_days):
            return None
        
        cls.record_check_time()
        return cls.get_update_info()


__all__ = ['UpdateChecker', 'CURRENT_VERSION']
