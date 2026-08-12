"""Entry point for the modern (HTML/CSS/JS) PC Cleaner UI.

Run with: python app_web.py
"""

import os

import webview

from api import Api
import backend
from remote.host_session import HostSession, load_resume_state

WEB_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "web")


def main():
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

    resume = load_resume_state()
    if resume:
        session = HostSession(
            label=resume["label"],
            code=resume["code"],
            ip=resume["ip"],
            port=resume["port"],
            unattended=resume.get("unattended", False),
        )
        api.host_session = session
        session.start()
    else:
        session = HostSession.resume_unattended()
        if session:
            api.host_session = session

    webview.start()


if __name__ == "__main__":
    main()
