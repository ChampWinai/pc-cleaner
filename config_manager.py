"""Configuration management for PC Cleaner."""
import json
import os
from pathlib import Path
from typing import Any, Dict, Optional
import logging

log = logging.getLogger(__name__)

CONFIG_DIR = Path(os.getenv('LOCALAPPDATA')) / 'PCCleaner'
CONFIG_FILE = CONFIG_DIR / 'settings.json'

DEFAULT_CONFIG = {
    'general': {
        'auto_start_on_login': False,
        'check_for_updates': True,
        'update_check_interval_days': 7,
        'enable_logging': True,
    },
    'cleaning': {
        'auto_clean_enabled': False,
        'auto_clean_schedule': 'daily',  # 'daily', 'weekly', 'monthly'
        'auto_clean_hour': 2,
        'auto_clean_minute': 0,
        'enable_confirmations': True,
        'skip_system_files': True,
    },
    'vault': {
        'auto_backup_enabled': True,
        'backup_retention_days': 30,
    },
    'ui': {
        'dark_mode': False,
        'startup_minimized': False,
        'auto_dismiss_scan_complete': False,
        'dismiss_after_seconds': 5,
    },
    'whitelist': {
        'folders': [],  # List of folder paths to exclude from cleaning
        'file_extensions': [],  # List of extensions to preserve
    },
    'features': {
        'enable_drivers_cleanup': True,
        'enable_temp_cleanup': True,
        'enable_startup_optimize': True,
        'enable_registry_cleanup': True,
        'enable_vault': True,
        'enable_duplicate_finder': True,
        'enable_large_files': True,
    },
}


class ConfigManager:
    """Manages application configuration with persistence to JSON."""

    def __init__(self):
        self.config = self._load_config()

    def _load_config(self) -> Dict[str, Any]:
        """Load config from file or return defaults."""
        try:
            CONFIG_DIR.mkdir(parents=True, exist_ok=True)
            if CONFIG_FILE.exists():
                with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                    return self._merge_with_defaults(config)
            else:
                self.save_config(DEFAULT_CONFIG)
                return DEFAULT_CONFIG.copy()
        except Exception as e:
            log.error(f"Failed to load config: {e}")
            return DEFAULT_CONFIG.copy()

    def _merge_with_defaults(self, config: Dict) -> Dict:
        """Merge loaded config with defaults to handle new fields."""
        merged = DEFAULT_CONFIG.copy()
        for key, value in config.items():
            if isinstance(value, dict) and key in merged:
                merged[key].update(value)
            else:
                merged[key] = value
        return merged

    def save_config(self, config: Optional[Dict] = None) -> bool:
        """Save config to file."""
        try:
            CONFIG_DIR.mkdir(parents=True, exist_ok=True)
            config_to_save = config or self.config
            with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
                json.dump(config_to_save, f, indent=2, ensure_ascii=False)
            self.config = config_to_save
            return True
        except Exception as e:
            log.error(f"Failed to save config: {e}")
            return False

    def get(self, key: str, default: Any = None) -> Any:
        """Get config value by dot-notation path (e.g., 'cleaning.auto_clean_enabled')."""
        keys = key.split('.')
        value = self.config
        for k in keys:
            if isinstance(value, dict):
                value = value.get(k)
            else:
                return default
        return value if value is not None else default

    def set(self, key: str, value: Any) -> bool:
        """Set config value by dot-notation path."""
        keys = key.split('.')
        config = self.config
        for k in keys[:-1]:
            if k not in config:
                config[k] = {}
            config = config[k]
        config[keys[-1]] = value
        return self.save_config()

    def add_whitelist_folder(self, folder: str) -> bool:
        """Add folder to whitelist."""
        whitelist = self.config.get('whitelist', {}).get('folders', [])
        if folder not in whitelist:
            whitelist.append(folder)
            return self.set('whitelist.folders', whitelist)
        return True

    def remove_whitelist_folder(self, folder: str) -> bool:
        """Remove folder from whitelist."""
        whitelist = self.config.get('whitelist', {}).get('folders', [])
        if folder in whitelist:
            whitelist.remove(folder)
            return self.set('whitelist.folders', whitelist)
        return True

    def get_whitelist_folders(self) -> list:
        """Get list of whitelisted folders."""
        return self.config.get('whitelist', {}).get('folders', [])

    def reset_to_defaults(self) -> bool:
        """Reset all config to defaults."""
        return self.save_config(DEFAULT_CONFIG.copy())


# Global config instance
config = ConfigManager()
