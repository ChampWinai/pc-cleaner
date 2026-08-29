"""JS-facing bridge exposed to the webview as `window.pywebview.api`.

Every method here is synchronous from Python's point of view; pywebview
already dispatches each call on its own worker thread, so a slow scan does
not freeze the window chrome.
"""

import webview
import logging

import backend
from config_manager import config
from history_db import history_db
from update_checker import UpdateChecker
from task_scheduler import TaskSchedulerManager
from operation_context import OperationContext

log = logging.getLogger(__name__)

# Track active operations for cancellation
_active_operations = {}


class Api:
    def __init__(self):
        self.window = None  # set by app_web.py after the window is created

    # ========================================================================
    # SCANNING & CLEANING
    # ========================================================================

    def scan(self, deep=False):
        def on_progress(label):
            if self.window:
                safe_label = label.replace("\\", "\\\\").replace("'", "\\'")
                self.window.evaluate_js(f"window.onScanProgress && window.onScanProgress('{safe_label}')")

        return backend.scan(deep=deep, on_progress=on_progress)

    def get_children(self, path):
        return backend.list_children(path)

    def clean(self, selected):
        freed, errors, _batch_id = backend.clean_items(selected)
        return {"freed": freed, "freed_human": backend.human_size(freed), "errors": errors}

    def ram_status(self):
        return backend.ram_status()

    def clean_ram(self):
        before = backend.ram_status()
        trimmed, skipped = backend.trim_process_working_sets()
        after = backend.ram_status()
        freed = max(0, before["used"] - after["used"])
        return {
            "trimmed": trimmed,
            "skipped": skipped,
            "freed": freed,
            "freed_human": backend.human_size(freed),
            "status": after,
        }

    def empty_recycle_bin(self):
        return {"success": backend.empty_recycle_bin()}

    # ========================================================================
    # VAULT (RECYCLE BIN)
    # ========================================================================

    def vault_list(self):
        entries = backend.vault_list()
        for e in entries:
            e["size_human"] = backend.human_size(e["size"])
            e["deleted_date"] = e["deleted_at"].split("T")[0]
        return entries

    def vault_restore(self, entry_id):
        return {"success": backend.restore_from_vault(entry_id)}

    def vault_purge(self, entry_id):
        backend.purge_vault_entry(entry_id)
        return {"success": True}

    def vault_purge_expired(self):
        backend.purge_expired_vault_entries()
        return {"success": True}

    def human_size(self, num_bytes):
        return backend.human_size(num_bytes)

    # ========================================================================
    # DOCKER
    # ========================================================================

    def docker_available(self):
        return backend.docker_available()

    def docker_prune(self):
        return backend.docker_prune()

    # ========================================================================
    # APP UNINSTALLER
    # ========================================================================

    def list_apps(self):
        apps = backend.list_installed_apps()
        for a in apps:
            a["size_human"] = backend.human_size(a["size"])
        return apps

    def uninstall_app(self, uninstall_string):
        return {"success": backend.uninstall_app(uninstall_string)}

    # ========================================================================
    # STARTUP MANAGER
    # ========================================================================

    def list_startup(self):
        return backend.list_startup_items()

    def disable_startup(self, item_id):
        success, message = backend.disable_startup_item(item_id)
        return {"success": success, "message": message}

    def enable_startup(self, item_id):
        success, message = backend.enable_startup_item(item_id)
        return {"success": success, "message": message}

    def delay_startup(self, item_id):
        success, message = backend.delay_startup_item(item_id)
        return {"success": success, "message": message}

    def undo_delay_startup(self, task_name):
        return {"success": backend.undo_delay_startup_item(task_name)}

    # ========================================================================
    # GAME MODE
    # ========================================================================

    def list_freezable_processes(self):
        items = backend.list_freezable_processes()
        for it in items:
            it["memory_human"] = backend.human_size(it["memory"])
        return items

    def game_mode_status(self):
        return {"active": backend.is_game_mode_active()}

    def enable_game_mode(self, process_names):
        count = backend.enable_game_mode(process_names)
        return {"frozen": count}

    def disable_game_mode(self):
        resumed, total = backend.disable_game_mode()
        return {"resumed": resumed, "total": total}

    # ========================================================================
    # SENSITIVE DATA SCANNER
    # ========================================================================

    def pick_folder(self):
        if not self.window:
            return None
        result = self.window.create_file_dialog(webview.FOLDER_DIALOG)
        return result[0] if result else None

    def scan_sensitive_data(self, folder):
        findings = backend.scan_sensitive_data(folder)
        return findings

    def shred_file(self, path):
        return {"success": backend.shred_file(path)}

    def vault_file(self, path, label):
        entry = backend.move_to_vault(path, f"privacy_{backend.uuid.uuid4().hex[:6]}", label)
        return {"success": True, "id": entry["id"]}

    # ========================================================================
    # AUTO CLEAN (SCHEDULED TASK)
    # ========================================================================

    def auto_clean_status(self):
        status = backend.auto_clean_status()
        if status.get("last_run"):
            status["last_run"]["ran_at_date"] = status["last_run"]["ran_at"].split("T")[0]
        return status

    def auto_clean_enable(self, interval_hours, deep):
        success, message = backend.auto_clean_enable(interval_hours=interval_hours, deep=deep)
        return {"success": success, "message": message}

    def auto_clean_disable(self):
        return {"success": backend.auto_clean_disable()}

    def auto_clean_run_now(self, deep=False):
        entry = backend.run_auto_clean(deep=deep)
        entry["ran_at_date"] = entry["ran_at"].split("T")[0]
        return entry

    # ========================================================================
    # HARDWARE & DRIVERS
    # ========================================================================

    def list_drivers(self):
        return backend.list_drivers()

    def check_driver_updates(self):
        return backend.check_driver_updates()

    def open_windows_update(self):
        return {"success": backend.open_windows_update()}

    # ========================================================================
    # CONFIGURATION MANAGEMENT
    # ========================================================================

    def get_config(self, key, default=None):
        """Get config value by dot-notation path."""
        try:
            return config.get(key, default)
        except Exception as e:
            log.error(f"Failed to get config '{key}': {e}")
            return default

    def set_config(self, key, value):
        """Set config value by dot-notation path."""
        try:
            return config.set(key, value)
        except Exception as e:
            log.error(f"Failed to set config '{key}': {e}")
            return False

    def get_all_config(self):
        """Get entire config dict."""
        return config.config

    def reset_config(self):
        """Reset all settings to defaults."""
        return config.reset_to_defaults()

    def get_whitelist(self):
        """Get list of whitelisted folders."""
        return config.get_whitelist_folders()

    def add_whitelist(self, folder):
        """Add folder to whitelist."""
        return config.add_whitelist_folder(folder)

    def remove_whitelist(self, folder):
        """Remove folder from whitelist."""
        return config.remove_whitelist_folder(folder)

    # ========================================================================
    # HISTORY & ANALYTICS
    # ========================================================================

    def get_history_stats(self):
        """Get aggregate statistics."""
        return history_db.get_stats()

    def get_recent_scans(self, limit=50):
        """Get recent scan history."""
        return history_db.get_recent_scans(limit)

    def get_scan_items(self, scan_id):
        """Get items cleaned in a specific scan."""
        return history_db.get_cleaned_items_by_scan(scan_id)

    def clear_old_history(self, days=30):
        """Clear history older than specified days."""
        deleted = history_db.clear_old_history(days)
        return {"deleted": deleted}

    # ========================================================================
    # UPDATE CHECKING
    # ========================================================================

    def check_for_updates(self):
        """Check for new version."""
        update_info = UpdateChecker.check_and_notify()
        if update_info:
            return {
                "available": True,
                "version": update_info.get('version'),
                "url": update_info.get('url'),
                "download_url": update_info.get('download_url'),
                "release_notes": update_info.get('release_notes'),
            }
        return {"available": False}

    # ========================================================================
    # AUTO-CLEAN SCHEDULING (TASK SCHEDULER)
    # ========================================================================

    def schedule_auto_clean(self, hour, minute, frequency):
        """Create scheduled auto-clean task."""
        success = TaskSchedulerManager.create_task(hour, minute, frequency)
        return {"success": success}

    def unschedule_auto_clean(self):
        """Remove scheduled auto-clean task."""
        success = TaskSchedulerManager.delete_task()
        return {"success": success}

    def get_auto_clean_schedule(self):
        """Check if auto-clean is scheduled."""
        status = TaskSchedulerManager.get_task_status()
        return status

    # ========================================================================
    # OPERATION CONTROL (CANCELLATION & PROGRESS)
    # ========================================================================

    def create_operation(self, operation_id):
        """Create a new operation context."""
        if operation_id not in _active_operations:
            _active_operations[operation_id] = OperationContext(operation_id)
        return {"operation_id": operation_id}

    def cancel_operation(self, operation_id):
        """Cancel an active operation."""
        if operation_id in _active_operations:
            _active_operations[operation_id].cancel()
            return {"success": True}
        return {"success": False}

    def get_operation_progress(self, operation_id):
        """Get progress of an active operation."""
        if operation_id in _active_operations:
            return _active_operations[operation_id].get_progress()
        return {"progress": 0, "total": 0, "percentage": 0}

    def cleanup_operation(self, operation_id):
        """Clean up an operation context."""
        if operation_id in _active_operations:
            del _active_operations[operation_id]
            return {"success": True}
        return {"success": False}

