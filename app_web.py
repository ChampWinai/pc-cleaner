"""Entry point for the modern (HTML/CSS/JS) PC Cleaner UI.

Run with: python app_web.py
"""

import os
import sys

import webview

from api import Api
import backend

WEB_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "web")


def main():
    if "--auto-clean" in sys.argv:
        # Headless entry point invoked by the "PCCleaner_AutoClean" Scheduled
        # Task -- no window, just scan/clean the safe targets and exit.
        backend.purge_expired_vault_entries()
        backend.run_auto_clean(deep="--deep" in sys.argv)
        return

    backend.purge_expired_vault_entries()
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
    api.window = window

    webview.start()


if __name__ == "__main__":
    main()
