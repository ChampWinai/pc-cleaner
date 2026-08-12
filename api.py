"""JS-facing bridge exposed to the webview as `window.pywebview.api`.

Every method here is synchronous from Python's point of view; pywebview
already dispatches each call on its own worker thread, so a slow scan does
not freeze the window chrome.
"""

import webview

import backend


class Api:
    def __init__(self):
        self.window = None  # set by app_web.py after the window is created

    def scan(self, deep=False):
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

    # -- Hardware & Driver update check ------------------------------------
    def list_drivers(self):
        return backend.list_drivers()

    def check_driver_updates(self):
        return backend.check_driver_updates()

    def open_windows_update(self):
        return {"success": backend.open_windows_update()}
