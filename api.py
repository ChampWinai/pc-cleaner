"""JS-facing bridge exposed to the webview as `window.pywebview.api`.

Every method here is synchronous from Python's point of view; pywebview
already dispatches each call on its own worker thread, so a slow scan does
not freeze the window chrome.
"""

import webview
import logging
import threading

import backend
from config_manager import config
from history_db import history_db
from update_checker import UpdateChecker, CURRENT_VERSION
from task_scheduler import TaskSchedulerManager
from operation_context import OperationContext
from i18n import i18n, _
from notifications import tray_manager, notification_manager
from email_reports import email_reporter, ScheduledEmailReports
from advanced_features import benchmark, cost_analysis, keyboard_shortcuts, duplicate_finder
from security_compliance import pii_detector, two_factor, audit_logger, gdpr_mode

log = logging.getLogger(__name__)

# Track active operations for cancellation
_active_operations = {}


class Api:
    def __init__(self):
        self.window = None  # set by app_web.py after the window is created
        self._update_info = None
        self._update_path = None
        self._update_state = {"state": "idle", "percent": 0, "message": ""}

    # ========================================================================
    # INTERNATIONALIZATION
    # ========================================================================

    def get_language(self):
        """Get current language."""
        return i18n.get_current_language()

    def set_language(self, language: str):
        """Set language (en or th)."""
        success = i18n.set_language(language)
        return {"success": success, "language": i18n.language}

    def get_available_languages(self):
        """Get available languages."""
        return i18n.get_available_languages()

    def translate_all(self):
        """Get all translations for current language."""
        return i18n.get_all_translations()

    # ========================================================================
    # SYSTEM TRAY & NOTIFICATIONS
    # ========================================================================

    def show_tray_icon(self):
        """Show system tray icon."""
        success = tray_manager.show()
        return {"success": success}

    def hide_tray_icon(self):
        """Hide system tray icon."""
        success = tray_manager.hide()
        return {"success": success}

    def send_notification(self, title: str, message: str, duration: int = 5):
        """Send desktop notification."""
        success = notification_manager.notify(title, message, duration)
        return {"success": success}

    def notify_scan_complete(self, items_found: int, total_size: str):
        """Notify scan completion."""
        success = notification_manager.notify_scan_complete(items_found, total_size)
        return {"success": success}

    def notify_clean_complete(self, freed: str, errors: int = 0):
        """Notify clean completion."""
        success = notification_manager.notify_clean_complete(freed, errors)
        return {"success": success}

    def notify_update_available(self, version: str):
        """Notify about update."""
        success = notification_manager.notify_update_available(version)
        return {"success": success}

    # ========================================================================
    # EMAIL REPORTS
    # ========================================================================

    def set_email_credentials(self, email: str, password: str):
        """Set email credentials for reporting."""
        success = email_reporter.set_credentials(email, password)
        return {"success": success}

    def send_scan_report(self, recipient_email: str, scan_type: str, items_found: int,
                        total_size_bytes: int, duration_seconds: float):
        """Send scan report via email."""
        success = email_reporter.send_scan_report(
            recipient_email, scan_type, items_found, total_size_bytes, duration_seconds
        )
        return {"success": success}

    def send_cleaning_report(self, recipient_email: str, freed_bytes: int, items_cleaned: int):
        """Send cleaning report via email."""
        success = email_reporter.send_cleaning_report(recipient_email, freed_bytes, items_cleaned)
        return {"success": success}

    # ========================================================================
    # PERFORMANCE BENCHMARKING
    # ========================================================================

    def benchmark_capture_baseline(self):
        """Capture baseline performance."""
        baseline = benchmark.capture_baseline()
        return baseline

    def benchmark_capture_current(self):
        """Capture current performance."""
        current = benchmark.capture_current()
        return current

    def benchmark_get_improvement(self):
        """Get performance improvements."""
        improvement = benchmark.get_improvement()
        return improvement

    # ========================================================================
    # COST ANALYSIS
    # ========================================================================

    def calculate_cost_saved(self, freed_bytes: int, region: str = 'thailand'):
        """Calculate monetary value of freed space."""
        result = cost_analysis.calculate_saved_cost(freed_bytes, region)
        return result

    # ========================================================================
    # KEYBOARD SHORTCUTS
    # ========================================================================

    def get_keyboard_shortcuts(self):
        """Get all keyboard shortcuts."""
        return keyboard_shortcuts.get_all_shortcuts()

    def get_shortcuts_help(self):
        """Get formatted shortcuts help."""
        return keyboard_shortcuts.get_help_text()

    # ========================================================================
    # DUPLICATE FINDER
    # ========================================================================

    def find_duplicates_by_hash(self, folder: str, extensions=None):
        """Find duplicate files by content hash."""
        result = duplicate_finder.find_by_hash(folder, extensions)
        return result

    def find_duplicates_by_name(self, folder: str):
        """Find duplicate files by name."""
        result = duplicate_finder.find_by_name(folder)
        return result

    # ========================================================================
    # SECURITY & COMPLIANCE
    # ========================================================================

    def scan_pii_folder(self, folder: str):
        """Scan folder for personally identifiable information."""
        findings = pii_detector.scan_folder(folder)
        return findings

    def request_2fa_confirmation(self, operation_name: str):
        """Request 2FA confirmation for sensitive operation."""
        op_id = f"op_{backend.uuid.uuid4().hex[:8]}"
        success = two_factor.request_confirmation(op_id, operation_name)
        return {"success": success, "operation_id": op_id}

    def confirm_2fa_operation(self, operation_id: str):
        """Confirm a 2FA protected operation."""
        success = two_factor.confirm_operation(operation_id)
        return {"success": success}

    def is_operation_confirmed(self, operation_id: str):
        """Check if operation has valid 2FA confirmation."""
        confirmed = two_factor.is_confirmed(operation_id)
        return {"confirmed": confirmed}

    def export_audit_log(self, output_file: str, format: str = 'csv', days: int = 30):
        """Export audit log to file."""
        if format == 'csv':
            success = audit_logger.export_csv(output_file, days)
        elif format == 'json':
            success = audit_logger.export_json(output_file, days)
        else:
            return {"success": False, "error": "Invalid format"}
        return {"success": success, "file": output_file}

    def enable_gdpr_mode(self):
        """Enable GDPR compliance mode."""
        success = gdpr_mode.enable()
        return {"success": success}

    def disable_gdpr_mode(self):
        """Disable GDPR compliance mode."""
        success = gdpr_mode.disable()
        return {"success": success}

    def purge_user_data(self, user_identifier: str):
        """Purge all user data (GDPR right-to-be-forgotten)."""
        success = gdpr_mode.purge_user_data(user_identifier)
        audit_logger.log_event(
            event_type='gdpr',
            user='system',
            action='purge_data',
            resource=user_identifier,
            status='success' if success else 'failed'
        )
        return {"success": success}

    # ========================================================================
    # SCANNING & CLEANING (EXISTING)
    # ========================================================================


    def scan(self, deep=False):
        # No evaluate_js progress callback: calling it from this worker thread
        # while the UI thread is busy can deadlock WebView2 ("Not Responding"),
        # and the scan finishes in well under a second anyway.
        return backend.scan(deep=deep)

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

    def check_for_updates(self, force=False):
        """Check for a new version (throttled to every 6h unless force)."""
        info = UpdateChecker.get_update_info() if force else UpdateChecker.check_and_notify()
        if not info:
            return {"available": False, "current": CURRENT_VERSION}
        self._update_info = info
        return {
            "available": True,
            "current": CURRENT_VERSION,
            "version": info['version'],
            "url": info['url'],
            "release_notes": info['release_notes'],
            "size": info['size'],
            "can_install": bool(info['sha256'] and info['download_url']),
        }

    def start_update(self):
        """Download + verify in a background thread; poll update_state()."""
        info = self._update_info
        if not info:
            return {"success": False, "message": "no update checked"}
        if self._update_state["state"] == "downloading":
            return {"success": True}
        self._update_state = {"state": "downloading", "percent": 0, "message": ""}

        def work():
            try:
                self._update_path = UpdateChecker.download_installer(
                    info, lambda f: self._update_state.update(percent=int(f * 100)))
                self._update_state = {"state": "ready", "percent": 100, "message": ""}
            except Exception as e:
                log.warning("update download failed: %s", e)
                self._update_state = {"state": "error", "percent": 0, "message": str(e)}
        threading.Thread(target=work, daemon=True).start()
        return {"success": True}

    def update_state(self):
        return self._update_state

    def install_update(self):
        """Run the verified installer, then close this window so files unlock."""
        if self._update_state["state"] != "ready":
            return {"success": False}
        UpdateChecker.run_installer(self._update_path)
        if self.window:
            self.window.destroy()
        return {"success": True}

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

    def remote_controller_stop(self):
        if self.controller_session:
            self.controller_session.stop()
        return {"success": True}

    # -- New Upgrades --------------------------------------------------------
    def network_flush(self):
        return backend.network_flush()

    def update_software_winget(self):
        return backend.update_software_winget()

    def scan_large_files(self, drive="C:\\", limit=50, min_size_mb=100):
        files = backend.scan_large_files(drive=drive, limit=limit, min_size_mb=min_size_mb)
        for f in files:
            f["size_human"] = backend.human_size(f["size"])
        return files

    def add_context_menu(self):
        return {"success": backend.add_context_menu()}

    def remove_context_menu(self):
        return {"success": backend.remove_context_menu()}

    # -- New Advanced Tools --------------------------------------------------
    def debloat_windows(self):
        import windows_optimizer
        return windows_optimizer.remove_bloatware()

    def disable_telemetry(self):
        import windows_optimizer
        return windows_optimizer.disable_telemetry()

    def clean_registry(self):
        import windows_optimizer
        return windows_optimizer.clean_registry()

    def find_duplicate_files(self, folder, mode="hash", extensions=None):
        import advanced_features
        finder = advanced_features.DuplicateFinderAdvanced()
        if mode == "name":
            return finder.find_by_name(folder)
        else:
            return finder.find_by_hash(folder, extensions)
