"""Entry point for the modern (HTML/CSS/JS) PC Cleaner UI.

Run with: python app_web.py
"""

import os
import sys
import threading

import webview

from api import Api
from notifications import tray_manager, notify_once
import backend

WEB_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "web")


def _enable_hang_dump():
    """PCCLEANER_DEBUG=1: dump every thread's stack to the log dir every 10s."""
    import faulthandler
    log_dir = os.path.join(os.environ.get("LOCALAPPDATA", "."), "PCCleaner", "logs")
    os.makedirs(log_dir, exist_ok=True)
    f = open(os.path.join(log_dir, "hang_dump.log"), "a")
    faulthandler.dump_traceback_later(10, repeat=True, file=f)


def _setup_tray(window):
    def quick_clean():
        entry = backend.run_auto_clean()
        tray_manager.notify("PC Cleaner", f"ล้างด่วนเสร็จ ได้พื้นที่คืน {entry['freed_human']}")

    def open_window():
        window.show()
        window.restore()

    tray_manager.on_click_restore = open_window
    tray_manager.on_click_clean = lambda: threading.Thread(target=quick_clean, daemon=True).start()
    tray_manager.on_click_quit = window.destroy
    tray_manager.show()
    window.events.closed += tray_manager.hide


def main():
    if os.environ.get("PCCLEANER_DEBUG"):
        _enable_hang_dump()
    if "--auto-clean" in sys.argv:
        # Headless entry point invoked by the "PCCleaner_AutoClean" Scheduled
        # Task -- no window, just scan/clean the safe targets and exit.
        # Skip if the previous hourly run is somehow still going.
        if not backend.acquire_single_instance("PCCleaner_AutoClean"):
            return
        backend.purge_expired_vault_entries()
        entry = backend.run_auto_clean(deep="--deep" in sys.argv)
        if backend.should_notify_junk(entry):
            notify_once("PC Cleaner", f"มีไฟล์ขยะที่ควรตรวจเอง {entry['review_human']} — เปิดโปรแกรมเพื่อดูรายการ")
        return

    # Second launch just brings the existing window forward.
    if not backend.acquire_single_instance("PCCleaner_Window"):
        backend.focus_existing_window()
        return

    # Purging a big expired vault can take minutes; don't block the window on it.
    threading.Thread(target=backend.purge_expired_vault_entries, daemon=True).start()
    api = Api()
    window = webview.create_window(
        "PC Cleaner",
        url=os.path.join(WEB_DIR, "index.html"),
        js_api=api,
        width=980,
        height=760,
        min_size=(760, 600),
        background_color="#0e0e16",
    )
    api._window = window
    _setup_tray(window)

    webview.start()


if __name__ == "__main__":
    main()
