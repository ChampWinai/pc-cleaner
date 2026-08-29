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

try:
    from win10toast import ToastNotifier
    HAS_TOAST = True
except ImportError:
    HAS_TOAST = False
    log.warning("win10toast not available; desktop notifications disabled")


class TrayManager:
    """Manage system tray icon and interactions."""

    def __init__(self, app_name: str = 'PC Cleaner', icon_path: Optional[str] = None):
        self.app_name = app_name
        self.icon_path = icon_path or self._get_default_icon()
        self.icon = None
        self.on_click_restore = None
        self.on_click_clean = None
        self.on_click_quit = None

    def _get_default_icon(self) -> str:
        """Get path to default app icon."""
        app_dir = Path(__file__).parent
        icon_path = app_dir / 'icon.ico'
        if icon_path.exists():
            return str(icon_path)
        # Fallback: create a simple 1x1 blue pixel
        return None

    def create_icon(self) -> bool:
        """Create and show system tray icon."""
        if not HAS_PYSTRAY:
            log.warning("pystray not installed; cannot create tray icon")
            return False

        try:
            if self.icon_path and Path(self.icon_path).exists():
                image = Image.open(self.icon_path)
            else:
                # Create a simple blue square if no icon available
                image = Image.new('RGB', (64, 64), color=(10, 132, 255))

            menu = Menu(
                MenuItem(f'🔍 {self.app_name}', lambda icon, item: self._handle_restore()),
                MenuItem('🧹 Scan Now', lambda icon, item: self._handle_scan()),
                MenuItem('⚙️ Settings', lambda icon, item: self._handle_settings()),
                Menu.SEPARATOR,
                MenuItem('❌ Exit', lambda icon, item: self._handle_quit()),
            )

            self.icon = Icon(self.app_name, image, menu=menu)
            log.info("System tray icon created successfully")
            return True
        except Exception as e:
            log.error(f"Failed to create tray icon: {e}")
            return False

    def show(self) -> bool:
        """Show tray icon."""
        if not self.icon:
            if not self.create_icon():
                return False
        try:
            self.icon.run_in_background()
            log.info("Tray icon displayed")
            return True
        except Exception as e:
            log.error(f"Failed to show tray icon: {e}")
            return False

    def hide(self) -> bool:
        """Hide tray icon."""
        if self.icon:
            try:
                self.icon.stop()
                log.info("Tray icon hidden")
                return True
            except Exception as e:
                log.error(f"Failed to hide tray icon: {e}")
        return False

    def _handle_restore(self):
        """Handle restore window click."""
        if self.on_click_restore:
            self.on_click_restore()

    def _handle_scan(self):
        """Handle scan click."""
        if self.on_click_clean:
            self.on_click_clean()

    def _handle_settings(self):
        """Handle settings click."""
        log.info("Settings requested from tray")

    def _handle_quit(self):
        """Handle quit click."""
        if self.on_click_quit:
            self.on_click_quit()

    def notify(self, title: str, message: str):
        """Show a system tray notification."""
        try:
            if HAS_PYSTRAY and self.icon:
                self.icon.notify(message, title)
                return True
        except Exception as e:
            log.debug(f"Tray notification failed: {e}")
        return False


class NotificationManager:
    """Manage desktop notifications."""

    def __init__(self, app_name: str = 'PC Cleaner'):
        self.app_name = app_name
        self.notifier = ToastNotifier() if HAS_TOAST else None

    def notify(self, title: str, message: str, duration: int = 5, icon: Optional[str] = None) -> bool:
        """Send desktop notification."""
        if not HAS_TOAST or not self.notifier:
            log.warning("Desktop notifications not available")
            return False

        try:
            self.notifier.show_toast(
                title=title,
                msg=message,
                duration=duration,
                threaded=True,
            )
            log.debug(f"Notification shown: {title} - {message}")
            return True
        except Exception as e:
            log.error(f"Failed to show notification: {e}")
            return False

    def notify_scan_complete(self, items_found: int, total_size: str) -> bool:
        """Notify scan completion."""
        return self.notify(
            title='🔍 Scan Complete',
            message=f'Found {items_found} items ({total_size})',
            duration=5
        )

    def notify_clean_complete(self, freed: str, errors: int = 0) -> bool:
        """Notify cleaning completion."""
        msg = f'Freed {freed}'
        if errors > 0:
            msg += f' ({errors} errors)'
        return self.notify(
            title='✨ Cleaning Complete',
            message=msg,
            duration=5
        )

    def notify_update_available(self, version: str) -> bool:
        """Notify about available update."""
        return self.notify(
            title='🎉 Update Available',
            message=f'PC Cleaner {version} is now available',
            duration=10
        )

    def notify_error(self, operation: str, error: str) -> bool:
        """Notify about an error."""
        return self.notify(
            title='⚠️ Error',
            message=f'{operation}: {error}',
            duration=7
        )

    def notify_vault_full(self, usage_percent: int) -> bool:
        """Notify about vault usage."""
        return self.notify(
            title='📦 Vault Status',
            message=f'Vault is {usage_percent}% full',
            duration=5
        )


# Global instances
tray_manager = TrayManager()
notification_manager = NotificationManager()

__all__ = ['TrayManager', 'NotificationManager', 'tray_manager', 'notification_manager']
