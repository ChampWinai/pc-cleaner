"""Internationalization (i18n) system for PC Cleaner."""
import json
import logging
from typing import Dict, Any, Optional
from pathlib import Path
import os

log = logging.getLogger(__name__)

# Translations dictionary
TRANSLATIONS = {
    'en': {
        # Navigation
        'nav_cleaner': 'Storage Cleaner',
        'nav_drivers': 'Driver Updates',
        'nav_game_mode': 'Game Mode',
        'nav_security': 'Security Tools',
        'nav_vault': 'Safety Vault',
        
        # Common buttons
        'btn_scan': 'Scan',
        'btn_clean': 'Clean',
        'btn_settings': 'Settings',
        'btn_cancel': 'Cancel',
        'btn_ok': 'OK',
        'btn_apply': 'Apply',
        
        # Status messages
        'msg_scanning': 'Scanning...',
        'msg_scan_complete': 'Scan complete',
        'msg_cleaning': 'Cleaning...',
        'msg_clean_complete': 'Cleaning complete',
        'msg_freed': 'Freed',
        'msg_error': 'Error',
        'msg_success': 'Success',
        
        # Settings
        'setting_language': 'Language',
        'setting_dark_mode': 'Dark Mode',
        'setting_auto_clean': 'Auto-Clean Schedule',
        'setting_notifications': 'Desktop Notifications',
        'setting_vault_retention': 'Vault Retention Days',
        
        # Features
        'feature_temp_files': 'Temporary Files',
        'feature_cache': 'Cache Files',
        'feature_drivers': 'Driver Updates',
        'feature_registry': 'Registry Cleanup',
        'feature_duplicates': 'Duplicate Files',
        'feature_large_files': 'Large Files',
        'feature_privacy': 'Privacy Scan',
    },
    'th': {
        # Navigation
        'nav_cleaner': 'ทำความสะอาด',
        'nav_drivers': 'อัปเดตไดรเวอร์',
        'nav_game_mode': 'โหมดเกม',
        'nav_security': 'เครื่องมือรักษาความปลอดภัย',
        'nav_vault': 'ตู้เซฟ',
        
        # Common buttons
        'btn_scan': 'สแกน',
        'btn_clean': 'ทำความสะอาด',
        'btn_settings': 'ตั้งค่า',
        'btn_cancel': 'ยกเลิก',
        'btn_ok': 'ตกลง',
        'btn_apply': 'ใช้งาน',
        
        # Status messages
        'msg_scanning': 'กำลังสแกน...',
        'msg_scan_complete': 'สแกนเสร็จสิ้น',
        'msg_cleaning': 'กำลังทำความสะอาด...',
        'msg_clean_complete': 'ทำความสะอาดเสร็จสิ้น',
        'msg_freed': 'เพิ่มพื้นที่ว่าง',
        'msg_error': 'ข้อผิดพลาด',
        'msg_success': 'สำเร็จ',
        
        # Settings
        'setting_language': 'ภาษา',
        'setting_dark_mode': 'โหมดมืด',
        'setting_auto_clean': 'ตั้งเวลาการทำความสะอาดอัตโนมัติ',
        'setting_notifications': 'การแจ้งเตือนบนเดสก์ทอป',
        'setting_vault_retention': 'วันการเก็บรักษาตู้เซฟ',
        
        # Features
        'feature_temp_files': 'ไฟล์ชั่วคราว',
        'feature_cache': 'ไฟล์แคช',
        'feature_drivers': 'อัปเดตไดรเวอร์',
        'feature_registry': 'ทำความสะอาดรีจิสทรี',
        'feature_duplicates': 'ไฟล์ที่ซ้ำกัน',
        'feature_large_files': 'ไฟล์ขนาดใหญ่',
        'feature_privacy': 'การสแกนความเป็นส่วนตัว',
    }
}


class I18n:
    """Internationalization manager."""

    def __init__(self, default_language: str = 'en'):
        self.language = default_language
        self.translations = TRANSLATIONS
        self._load_language_preference()

    def _load_language_preference(self):
        """Load saved language preference from config."""
        try:
            from config_manager import config
            lang = config.get('general.language', 'en')
            if lang in self.translations:
                self.language = lang
        except Exception as e:
            log.debug(f"Failed to load language preference: {e}")

    def set_language(self, language: str) -> bool:
        """Set active language."""
        if language not in self.translations:
            log.warning(f"Language '{language}' not available")
            return False

        self.language = language

        # Save to config
        try:
            from config_manager import config
            config.set('general.language', language)
        except Exception as e:
            log.error(f"Failed to save language preference: {e}")

        return True

    def translate(self, key: str, default: str = None) -> str:
        """Translate a key to current language."""
        try:
            translation = self.translations.get(self.language, {}).get(key)
            if translation:
                return translation

            # Fall back to English
            translation = self.translations.get('en', {}).get(key)
            if translation:
                return translation

            # Return default or key itself
            return default or key
        except Exception as e:
            log.error(f"Translation error for key '{key}': {e}")
            return default or key

    def _(self, key: str) -> str:
        """Shorthand for translate()."""
        return self.translate(key)

    def get_available_languages(self) -> Dict[str, str]:
        """Get list of available languages."""
        return {
            'en': 'English',
            'th': 'ไทย',
        }

    def get_current_language(self) -> str:
        """Get current language code."""
        return self.language

    def get_all_translations(self) -> Dict[str, Any]:
        """Get all translations for current language as JSON."""
        return self.translations.get(self.language, {})


# Global i18n instance
i18n = I18n()


def translate(key: str, default: str = None) -> str:
    """Global translate function."""
    return i18n.translate(key, default)


def _(key: str) -> str:
    """Shorthand for translate()."""
    return i18n.translate(key)


__all__ = ['I18n', 'i18n', 'translate', '_']
