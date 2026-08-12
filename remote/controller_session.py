"""Controller side of a remote-assistance session: the technician's PC.

Connects directly to the host, which listens on its own LAN address. The
user pastes one "connect code" (format `SECRET@ip:port`, produced by
HostSession) -- there is nothing else to configure.

Same threaded-asyncio-loop-with-polled-state pattern as HostSession, mirrored
so `api.py` can expose simple synchronous getters/setters to the JS UI.
"""

import asyncio
import threading

import websockets

from remote import protocol
from remote.crypto import SessionCipher


def parse_connect_code(connect_code: str):
    """'SECRET@ip:port' -> (secret, ip, port). Raises ValueError if malformed."""
    connect_code = connect_code.strip()
    secret, _, address = connect_code.partition("@")
    ip, _, port = address.rpartition(":")
    if not secret or not ip or not port.isdigit():
        raise ValueError("Invalid connect code")
    return secret, ip, int(port)


class ControllerSession:
    def __init__(self, connect_code: str, label="Technician"):
        self.connect_code = connect_code
        self.label = label
        self.code, self.host_ip, self.host_port = parse_connect_code(connect_code)
        self.cipher = SessionCipher(self.code)

        self._lock = threading.Lock()
        self.status = "connecting"  # connecting -> awaiting_permission -> active/denied -> ended
        self.view_only = False
        self.latest_frame = None  # {"data": b64, "w":, "h":}
        self.latest_telemetry = None
        self.latest_diagnostic_report = None
        self.last_action_result = None
        self.last_error = None

        self._loop = None
        self._ws = None
        self._thread = None
        self._stop_evt = threading.Event()

    def start(self):
        self._thread = threading.Thread(target=self._run_loop, daemon=True)
        self._thread.start()

    def stop(self):
        self._stop_evt.set()
        if self._loop and self._ws:
            asyncio.run_coroutine_threadsafe(self._send(protocol.DISCONNECT), self._loop)
            asyncio.run_coroutine_threadsafe(self._safe_close(), self._loop)
        with self._lock:
            self.status = "ended"

    def get_status(self):
        with self._lock:
            return {"status": self.status, "view_only": self.view_only, "last_error": self.last_error}

    def get_frame(self):
        with self._lock:
            return self.latest_frame

    def get_telemetry(self):
        with self._lock:
            return self.latest_telemetry

    def pop_diagnostic_report(self):
        with self._lock:
            report, self.latest_diagnostic_report = self.latest_diagnostic_report, None
            return report

    def pop_action_result(self):
        with self._lock:
            result, self.last_action_result = self.last_action_result, None
            return result

    def set_view_only(self, value: bool):
        with self._lock:
            self.view_only = bool(value)
        if self._loop:
            asyncio.run_coroutine_threadsafe(
                self._send(protocol.SET_VIEW_ONLY, value=bool(value)), self._loop
            )

    def send_input(self, kind, **fields):
        with self._lock:
            if self.view_only or self.status != "active":
                return
        if self._loop:
            asyncio.run_coroutine_threadsafe(self._send(protocol.INPUT_EVENT, kind=kind, **fields), self._loop)

    def request_action(self, action_id):
        if self._loop:
            asyncio.run_coroutine_threadsafe(
                self._send(protocol.ACTION_REQUEST, action_id=action_id), self._loop
            )

    def request_diagnostic_report(self):
        if self._loop:
            asyncio.run_coroutine_threadsafe(self._send(protocol.DIAGNOSTIC_REQUEST), self._loop)

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

    async def _send(self, msg_type, **fields):
        if self._ws is None:
            return
        try:
            await self._ws.send(protocol.pack(self.cipher, msg_type, **fields))
        except Exception:
            pass

    async def _main(self):
        url = f"ws://{self.host_ip}:{self.host_port}"
        async with websockets.connect(url, max_size=4 * 1024 * 1024) as ws:
            self._ws = ws
            await ws.send(protocol.pack(self.cipher, protocol.HELLO, role="controller", label=self.label))
            with self._lock:
                self.status = "awaiting_permission"

            async for raw in ws:
                msg = protocol.unpack(self.cipher, raw)
                await self._handle_message(msg)

    async def _handle_message(self, msg):
        mtype = msg["type"]
        if mtype == protocol.PERMISSION_RESPONSE:
            with self._lock:
                self.status = "active" if msg.get("allowed") else "denied"
        elif mtype == protocol.FRAME:
            with self._lock:
                self.latest_frame = {"data": msg["data"], "w": msg.get("w"), "h": msg.get("h")}
        elif mtype == protocol.TELEMETRY:
            with self._lock:
                self.latest_telemetry = msg["data"]
        elif mtype == protocol.DIAGNOSTIC_REPORT:
            with self._lock:
                self.latest_diagnostic_report = msg["data"]
        elif mtype == protocol.ACTION_RESULT:
            with self._lock:
                self.last_action_result = {"action_id": msg.get("action_id"), **msg.get("result", {})}
