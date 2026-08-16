"""JS-facing bridge exposed to the webview as `window.pywebview.api`.

Every method here is synchronous from Python's point of view; pywebview
already dispatches each call on its own worker thread, so a slow scan does
not freeze the window chrome.
"""

import webview

import backend
from remote import actions as remote_actions, trust_store, audit_log
from remote.host_session import HostSession, reboot_and_resume, get_lan_ip
from remote.controller_session import ControllerSession


class Api:
    def __init__(self):
        self.window = None  # set by app_web.py after the window is created
        self.host_session = None
        self.controller_session = None

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

    # -- Docker ----------------------------------------------------------
    def docker_available(self):
        return backend.docker_available()

    def docker_prune(self):
        return backend.docker_prune()

    # -- App Uninstaller ---------------------------------------------------
    def list_apps(self):
        apps = backend.list_installed_apps()
        for a in apps:
            a["size_human"] = backend.human_size(a["size"])
        return apps

    def uninstall_app(self, uninstall_string):
        return {"success": backend.uninstall_app(uninstall_string)}

    # -- Startup Manager ---------------------------------------------------
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

    # -- Game Mode ---------------------------------------------------------
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

    # -- Sensitive Data Scanner ---------------------------------------------
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

    # -- Auto Clean (hourly Scheduled Task) ---------------------------------
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

    # -- Hardware & Driver update check ------------------------------------
    def list_drivers(self):
        return backend.list_drivers()

    def check_driver_updates(self):
        return backend.check_driver_updates()

    def open_windows_update(self):
        return {"success": backend.open_windows_update()}

    # -- Remote Assistance ---------------------------------------------------
    def remote_list_actions(self):
        return remote_actions.list_actions()

    def remote_host_start(self, label):
        if self.host_session and self.host_session.get_status()["status"] not in ("ended",):
            self.host_session.stop()
        self.host_session = HostSession(label=label or "This PC")
        return self.host_session.start()

    def remote_host_status(self):
        if not self.host_session:
            return {"status": "idle"}
        return self.host_session.get_status()

    def remote_host_set_view_only(self, value):
        if self.host_session:
            self.host_session.set_view_only(value)
        return {"success": True}

    def remote_host_stop(self):
        if self.host_session:
            self.host_session.stop()
        return {"success": True}

    def remote_host_reboot_and_resume(self):
        if not self.host_session:
            return {"success": False}
        reboot_and_resume(self.host_session)
        return {"success": True}

    # -- Unattended Access (explicit opt-in) ---------------------------------
    def remote_unattended_status(self):
        data = trust_store.load()
        if not data or not data.get("enabled"):
            return {"enabled": False}
        connect_code = (
            self.host_session.connect_code
            if self.host_session and getattr(self.host_session, "unattended", False)
            else f"{data['code']}@{get_lan_ip()}:{data['port']}"
        )
        active = bool(
            self.host_session
            and getattr(self.host_session, "unattended", False)
            and self.host_session.get_status()["status"] not in ("ended",)
        )
        return {"enabled": True, "connect_code": connect_code, "active": active}

    def remote_unattended_enable(self, label):
        if self.host_session and self.host_session.get_status()["status"] not in ("ended",):
            self.host_session.stop()
        self.host_session = HostSession.enable_unattended(label=label or "This PC")
        return {"connect_code": self.host_session.connect_code}

    def remote_unattended_disable(self):
        HostSession.disable_unattended()
        if self.host_session and getattr(self.host_session, "unattended", False):
            self.host_session.stop()
        return {"success": True}

    def remote_audit_log(self):
        return audit_log.get_events(50)

    def remote_controller_start(self, connect_code, label):
        if self.controller_session and self.controller_session.get_status()["status"] != "ended":
            self.controller_session.stop()
        try:
            self.controller_session = ControllerSession(connect_code=connect_code, label=label or "Technician")
        except ValueError:
            return {"success": False, "message": "รหัสเชื่อมต่อไม่ถูกต้อง"}
        self.controller_session.start()
        return {"success": True}

    def remote_controller_status(self):
        if not self.controller_session:
            return {"status": "idle"}
        return self.controller_session.get_status()

    def remote_controller_frame(self):
        if not self.controller_session:
            return None
        return self.controller_session.get_frame()

    def remote_controller_telemetry(self):
        if not self.controller_session:
            return None
        return self.controller_session.get_telemetry()

    def remote_controller_diagnostic_report(self):
        if not self.controller_session:
            return None
        return self.controller_session.pop_diagnostic_report()

    def remote_controller_request_diagnostic_report(self):
        if self.controller_session:
            self.controller_session.request_diagnostic_report()
        return {"success": True}

    def remote_controller_action_result(self):
        if not self.controller_session:
            return None
        return self.controller_session.pop_action_result()

    def remote_controller_request_action(self, action_id):
        if self.controller_session:
            self.controller_session.request_action(action_id)
        return {"success": True}

    def remote_controller_set_view_only(self, value):
        if self.controller_session:
            self.controller_session.set_view_only(value)
        return {"success": True}

    def remote_controller_input(self, kind, payload):
        if self.controller_session:
            self.controller_session.send_input(kind, **(payload or {}))
        return {"success": True}

    def remote_controller_stop(self):
        if self.controller_session:
            self.controller_session.stop()
        return {"success": True}
