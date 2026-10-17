"""System tray and desktop notifications for PC Cleaner."""
import logging
from pathlib import Path
import os
from typing import Optional, Callable

log = logging.getLogger(__name__)

try:
    from pystray import Icon, Menu, MenuItem
    from PIL import Image
    HAS_PYSTRAY = True
except ImportError:
    HAS_PYSTRAY = False
    log.warning("pystray not available; system tray disabled")



def _tray_image():
    """Green rounded-square mark drawn at runtime, so no .ico file is needed."""
    from PIL import ImageDraw
    img = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle((2, 2, 62, 62), radius=16, fill=(34, 197, 94, 255))
    d.polygon([(32, 12), (37, 27), (52, 32), (37, 37), (32, 52), (27, 37), (12, 32), (27, 27)],
              fill=(4, 33, 15, 255))
    return img


class TrayManager:
    """Tray icon: open window, quick (safe-only) clean, quit."""

    def __init__(self, app_name: str = 'PC Cleaner'):
        self.app_name = app_name
        self.icon = None
        self.on_click_restore: Optional[Callable] = None
        self.on_click_clean: Optional[Callable] = None
        self.on_click_quit: Optional[Callable] = None

    def show(self) -> bool:
        if not HAS_PYSTRAY:
            return False
        if self.icon:
            return True
        try:
            menu = Menu(
                MenuItem('เปิด PC Cleaner', lambda i, it: self._call(self.on_click_restore), default=True),
                MenuItem('ล้างด่วน (เฉพาะที่ปลอดภัย)', lambda i, it: self._call(self.on_click_clean)),
                Menu.SEPARATOR,
                MenuItem('ออก', lambda i, it: self._call(self.on_click_quit)),
            )
            self.icon = Icon(self.app_name, _tray_image(), self.app_name, menu)
            self.icon.run_detached()
            return True
        except Exception as e:
            log.error(f"Failed to show tray icon: {e}")
            self.icon = None
            return False

    def hide(self) -> bool:
        if not self.icon:
            return False
        try:
            self.icon.stop()
        except Exception as e:
            log.debug(f"Tray stop failed: {e}")
        self.icon = None
        return True

    @staticmethod
    def _call(fn):
        if fn:
            fn()

    def notify(self, title: str, message: str) -> bool:
        try:
            if self.icon:
                self.icon.notify(message, title)
                return True
        except Exception as e:
            log.debug(f"Tray notification failed: {e}")
        return False


def notify_once(title: str, message: str, seconds: float = 8) -> bool:
    """Toast from a process with no tray icon (the headless Auto Clean run):
    show a temporary icon long enough for Windows to display the toast."""
    if not HAS_PYSTRAY:
        return False
    import time
    try:
        icon = Icon("PC Cleaner", _tray_image(), "PC Cleaner")
        icon.run_detached()
        time.sleep(0.5)
        icon.notify(message, title)
        time.sleep(seconds)
        icon.stop()
        return True
    except Exception as e:
        log.debug(f"notify_once failed: {e}")
        return False


class NotificationManager:
    """Manage desktop notifications."""

    def __init__(self, app_name: str = 'PC Cleaner'):
        self.app_name = app_name

    def notify(self, title: str, message: str, duration: int = 5, icon: Optional[str] = None) -> bool:
        """Toast via the tray icon if it's up, else a temporary one (pystray
        only -- win10toast was dropped: unmaintained and broken on new setuptools)."""
        if tray_manager.notify(title, message):
            return True
        import threading
        threading.Thread(target=notify_once, args=(title, message, duration), daemon=True).start()
        return HAS_PYSTRAY

    def notify_scan_complete(self, items_found: int, total_size: str) -> bool:
        """Notify scan completion."""
        return self.notify(
            title='Scan Complete',
            message=f'Found {items_found} items ({total_size})',
            duration=5
        )

    def notify_clean_complete(self, freed: str, errors: int = 0) -> bool:
        """Notify cleaning completion."""
        msg = f'Freed {freed}'
        if errors > 0:
            msg += f' ({errors} errors)'
        return self.notify(
            title='Cleaning Complete',
            message=msg,
            duration=5
        )

    def notify_update_available(self, version: str) -> bool:
        """Notify about available update."""
        return self.notify(
            title='Update Available',
            message=f'PC Cleaner {version} is now available',
            duration=10
        )

    def notify_error(self, operation: str, error: str) -> bool:
        """Notify about an error."""
        return self.notify(
            title='Error',
            message=f'{operation}: {error}',
            duration=7
        )

    def notify_vault_full(self, usage_percent: int) -> bool:
        """Notify about vault usage."""
        return self.notify(
            title='Vault Status',
            message=f'Vault is {usage_percent}% full',
            duration=5
        )


# Global instances
tray_manager = TrayManager()
notification_manager = NotificationManager()

__all__ = ['TrayManager', 'NotificationManager', 'tray_manager', 'notification_manager', 'notify_once']
