"""Host side of a remote-assistance session: the PC being helped.

The host IS the server: it listens directly on the LAN for one controller
connection, so there is nothing for the user to type (no relay address, no
port). The single "connect code" shown to the user already encodes the
host's address and the encryption secret (`CODE@ip:port`) -- the controller
just pastes that one string in.

For controllers outside the LAN (no direct route to the host), an optional
relay (`remote.relay_server`) can still be used manually -- see that module
-- but it is not part of the default flow.

Runs its own asyncio event loop on a background thread. All cross-thread
communication with the pywebview UI thread happens through plain
lock-protected attributes that `api.py` polls / sets.
"""

import asyncio
import base64
import io
import json
import socket
import threading
import time
import tkinter as tk
from tkinter import font as tkfont

import mss
import websockets
from PIL import Image

from remote import protocol, telemetry, actions, trust_store, audit_log
from remote.crypto import SessionCipher, generate_session_code

FRAME_INTERVAL = 1 / 8  # ~8 fps, kept modest for bandwidth
JPEG_QUALITY = 55
TELEMETRY_INTERVAL = 2.0


def get_lan_ip():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("8.8.8.8", 80))
        return s.getsockname()[0]
    except Exception:
        return "127.0.0.1"
    finally:
        s.close()


def get_free_port():
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.bind(("", 0))
    port = s.getsockname()[1]
    s.close()
    return port


class HostSession:
    def __init__(self, label="This PC", code=None, ip=None, port=None, unattended=False):
        self.label = label
        self.code = code or generate_session_code()
        self.cipher = SessionCipher(self.code)
        self.ip = ip or get_lan_ip()
        self.port = port or get_free_port()
        self.connect_code = f"{self.code}@{self.ip}:{self.port}"
        self.unattended = unattended

        self._lock = threading.Lock()
        self.status = "waiting"  # waiting -> pending_permission -> active -> ended
        self.view_only = False
        self.last_action_result = None
        self.last_error = None

        self._loop = None
        self._ws = None
        self._claimed = False
        self._thread = None
        self._stop_evt = threading.Event()
        self._overlay = None

    # -- lifecycle ----------------------------------------------------
    def start(self):
        self._thread = threading.Thread(target=self._run_loop, daemon=True)
        self._thread.start()
        return {"code": self.connect_code}

    def stop(self):
        self._stop_evt.set()
        if self._loop and self._ws:
            asyncio.run_coroutine_threadsafe(self._safe_close(), self._loop)
        self._teardown_overlay()
        with self._lock:
            self.status = "ended"

    def get_status(self):
        with self._lock:
            return {
                "status": self.status,
                "view_only": self.view_only,
                "code": self.connect_code,
                "last_action_result": self.last_action_result,
                "last_error": self.last_error,
            }

    def set_view_only(self, value: bool):
        with self._lock:
            self.view_only = bool(value)

    # -- Unattended Access (explicit opt-in, see trust_store.py) --------
    @classmethod
    def enable_unattended(cls, label="This PC"):
        """First-time opt-in: mint a persistent code/port and start hosting.
        Caller (api.py) is responsible for having already shown the user a
        confirm dialog before calling this.
        """
        code = generate_session_code()
        port = get_free_port()
        trust_store.save({"enabled": True, "code": code, "port": port, "label": label})
        session = cls(label=label, code=code, ip=get_lan_ip(), port=port, unattended=True)
        session.start()
        return session

    @classmethod
    def resume_unattended(cls, label=None):
        """Re-start hosting with the previously-approved persistent code, e.g.
        on app launch. Returns None if unattended access was never enabled.
        """
        data = trust_store.load()
        if not data or not data.get("enabled"):
            return None
        session = cls(
            label=label or data.get("label", "This PC"),
            code=data["code"],
            ip=get_lan_ip(),
            port=data["port"],
            unattended=True,
        )
        session.start()
        return session

    @staticmethod
    def disable_unattended():
        trust_store.clear()

    # -- asyncio side ---------------------------------------------------
    def _run_loop(self):
        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)
        try:
            self._loop.run_until_complete(self._main())
        except Exception as exc:
            with self._lock:
                self.last_error = str(exc)
                self.status = "ended"

    async def _safe_close(self):
        try:
            await self._ws.close()
        except Exception:
            pass

    async def _main(self):
        done = asyncio.Event()

        async def handler(ws):
            if self._claimed:
                await ws.close(code=4002, reason="a controller is already connected")
                return
            self._claimed = True
            self._ws = ws
            try:
                await self._session(ws)
            finally:
                done.set()

        async with websockets.serve(handler, "0.0.0.0", self.port, max_size=4 * 1024 * 1024):
            wait_task = asyncio.create_task(done.wait())
            stop_task = asyncio.create_task(self._wait_stop())
            await asyncio.wait([wait_task, stop_task], return_when=asyncio.FIRST_COMPLETED)
            with self._lock:
                if self.status not in ("ended",):
                    self.status = "ended"

    async def _wait_stop(self):
        while not self._stop_evt.is_set():
            await asyncio.sleep(0.2)

    async def _session(self, ws):
        # First message must decrypt with our session key -- if it doesn't,
        # the connect code was wrong; drop silently.
        try:
            raw = await asyncio.wait_for(ws.recv(), timeout=30)
            msg = protocol.unpack(self.cipher, raw)
        except Exception:
            await ws.close()
            return
        if msg.get("type") != protocol.HELLO or msg.get("role") != "controller":
            await ws.close()
            return
        controller_label = msg.get("label", "Technician")

        if self.unattended:
            # Pre-approved via an earlier explicit opt-in (trust_store) --
            # skip the per-session prompt, but everything else (visible
            # overlay, kill switch, audit log) still applies.
            allowed = True
        else:
            with self._lock:
                self.status = "pending_permission"
            allowed = await self._loop.run_in_executor(None, self._ask_permission, controller_label)

        await ws.send(protocol.pack(self.cipher, protocol.PERMISSION_RESPONSE, allowed=allowed))
        audit_log.log_event({
            "event": "connect_attempt",
            "controller": controller_label,
            "allowed": allowed,
            "unattended": self.unattended,
        })
        if not allowed:
            with self._lock:
                self.status = "ended"
            await ws.close()
            return

        with self._lock:
            self.status = "active"
        self._show_overlay(controller_label)
        session_started = time.time()

        capture_task = asyncio.create_task(self._capture_loop(ws))
        telemetry_task = asyncio.create_task(self._telemetry_loop(ws))
        try:
            async for raw in ws:
                msg = protocol.unpack(self.cipher, raw)
                await self._handle_message(ws, msg)
        finally:
            capture_task.cancel()
            telemetry_task.cancel()
            self._teardown_overlay()
            audit_log.log_event({
                "event": "session_end",
                "controller": controller_label,
                "duration_sec": round(time.time() - session_started, 1),
            })
            with self._lock:
                self.status = "ended"

    def _ask_permission(self, controller_label):
        """Blocking native dialog; runs on a worker thread, not the asyncio loop."""
        result = {"allowed": False}

        def build():
            root = tk.Tk()
            root.title("คำขอเชื่อมต่อรีโมท")
            root.attributes("-topmost", True)
            root.resizable(False, False)
            w, h = 420, 180
            root.geometry(f"{w}x{h}+{(root.winfo_screenwidth() - w)//2}+{(root.winfo_screenheight() - h)//2}")

            bold = tkfont.Font(weight="bold", size=11)
            tk.Label(root, text="คำขอเชื่อมต่อรีโมท", font=bold).pack(pady=(16, 4))
            tk.Label(
                root,
                text=f'"{controller_label}" ต้องการเชื่อมต่อเข้ามาดู/ควบคุมเครื่องนี้\nอนุญาตหรือไม่?',
                justify="center",
            ).pack(pady=4)

            btns = tk.Frame(root)
            btns.pack(pady=16)

            def allow():
                result["allowed"] = True
                root.destroy()

            def deny():
                result["allowed"] = False
                root.destroy()

            tk.Button(btns, text="ปฏิเสธ", width=12, command=deny).pack(side="left", padx=8)
            tk.Button(btns, text="อนุญาต", width=12, command=allow, bg="#2ecc71").pack(side="left", padx=8)
            root.protocol("WM_DELETE_WINDOW", deny)
            root.mainloop()

        build()
        return result["allowed"]

    def _show_overlay(self, controller_label):
        def build():
            root = tk.Tk()
            root.overrideredirect(True)
            root.attributes("-topmost", True)
            root.attributes("-alpha", 0.9)
            sw, sh = root.winfo_screenwidth(), root.winfo_screenheight()
            root.geometry(f"{sw}x{sh}+0+0")
            root.config(bg="black")
            root.attributes("-transparentcolor", "black")

            border = 6
            canvas = tk.Canvas(root, width=sw, height=sh, bg="black", highlightthickness=0)
            canvas.pack(fill="both", expand=True)
            neon = "#39ff88"
            canvas.create_rectangle(border // 2, border // 2, sw - border // 2, sh - border // 2, outline=neon, width=border)

            banner = tk.Frame(root, bg="#111", highlightbackground=neon, highlightthickness=1)
            banner.place(x=20, y=20)
            mode_note = " (Unattended Access)" if self.unattended else ""
            tk.Label(banner, text=f"กำลังเชื่อมต่อรีโมท — {controller_label}{mode_note}", bg="#111", fg=neon, padx=10, pady=6).pack(side="left")
            kill_btn = tk.Button(
                banner, text="ตัดการเชื่อมต่อทันที", bg="#e74c3c", fg="white",
                command=lambda: self.stop(),
            )
            kill_btn.pack(side="left", padx=(0, 6), pady=4)

            self._overlay = root
            root.mainloop()

        threading.Thread(target=build, daemon=True).start()

    def _teardown_overlay(self):
        if self._overlay is not None:
            try:
                self._overlay.after(0, self._overlay.destroy)
            except Exception:
                pass
            self._overlay = None

    async def _capture_loop(self, ws):
        with mss.mss() as sct:
            monitor = sct.monitors[0]
            while True:
                start = time.monotonic()
                img = sct.grab(monitor)
                pil = Image.frombytes("RGB", img.size, img.rgb)
                pil.thumbnail((1280, 800))
                buf = io.BytesIO()
                pil.save(buf, format="JPEG", quality=JPEG_QUALITY)
                data = base64.b64encode(buf.getvalue()).decode("ascii")
                await ws.send(protocol.pack(self.cipher, protocol.FRAME, data=data, w=pil.width, h=pil.height))
                elapsed = time.monotonic() - start
                await asyncio.sleep(max(0.0, FRAME_INTERVAL - elapsed))

    async def _telemetry_loop(self, ws):
        while True:
            snap = await self._loop.run_in_executor(None, telemetry.snapshot)
            await ws.send(protocol.pack(self.cipher, protocol.TELEMETRY, data=snap))
            await asyncio.sleep(TELEMETRY_INTERVAL)

    async def _handle_message(self, ws, msg):
        mtype = msg["type"]
        if mtype == protocol.INPUT_EVENT:
            with self._lock:
                if self.view_only:
                    return
            self._apply_input(msg)
        elif mtype == protocol.SET_VIEW_ONLY:
            self.set_view_only(msg.get("value", False))
        elif mtype == protocol.ACTION_REQUEST:
            with self._lock:
                blocked = self.view_only
            if blocked:
                result = {"success": False, "message": "ปฏิเสธ: เครื่องนี้อยู่ในโหมดดูอย่างเดียว (View-Only)"}
            else:
                result = await self._loop.run_in_executor(None, actions.run_action, msg.get("action_id"))
            with self._lock:
                self.last_action_result = result
            await ws.send(protocol.pack(self.cipher, protocol.ACTION_RESULT, action_id=msg.get("action_id"), result=result))
        elif mtype == protocol.DIAGNOSTIC_REQUEST:
            report = await self._loop.run_in_executor(None, telemetry.diagnostic_report)
            await ws.send(protocol.pack(self.cipher, protocol.DIAGNOSTIC_REPORT, data=report))
        elif mtype == protocol.DISCONNECT:
            self._stop_evt.set()
            await ws.close()

    def _apply_input(self, msg):
        try:
            import pyautogui
            pyautogui.FAILSAFE = False
            kind = msg.get("kind")
            if kind == "move":
                pyautogui.moveTo(msg["x"], msg["y"], _pause=False)
            elif kind == "click":
                pyautogui.click(msg["x"], msg["y"], button=msg.get("button", "left"), _pause=False)
            elif kind == "scroll":
                pyautogui.scroll(msg.get("amount", 0), _pause=False)
            elif kind == "key":
                pyautogui.press(msg["key"], _pause=False)
            elif kind == "type":
                pyautogui.typewrite(msg.get("text", ""), _pause=False)
        except Exception:
            pass


def get_state_file_path():
    import os
    return os.path.join(os.path.expanduser("~"), ".pc_cleaner_remote_resume.json")


def save_resume_state(session: HostSession):
    data = {
        "code": session.code,
        "ip": session.ip,
        "port": session.port,
        "label": session.label,
        "unattended": session.unattended,
        "saved_at": time.time(),
    }
    with open(get_state_file_path(), "w", encoding="utf-8") as f:
        json.dump(data, f)


def load_resume_state(max_age_seconds=900):
    import os
    path = get_state_file_path()
    if not os.path.exists(path):
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        if time.time() - data.get("saved_at", 0) > max_age_seconds:
            os.remove(path)
            return None
        os.remove(path)
        return data
    except Exception:
        return None


def reboot_and_resume(session: HostSession):
    """Persist session info then trigger a Windows restart."""
    save_resume_state(session)
    import subprocess
    subprocess.Popen(["shutdown", "/r", "/t", "5"])
