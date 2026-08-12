"""Message envelope encoding for the remote-assistance channel.

Every message is a small JSON dict with a "type" key, encrypted as a whole
with the session's SessionCipher before being sent over the relay
websocket. The relay only ever handles the resulting opaque bytes.
"""

import json

from remote.crypto import SessionCipher

# Message types
HELLO = "hello"                    # peer announces itself (host/controller)
PERMISSION_REQUEST = "permission_request"
PERMISSION_RESPONSE = "permission_response"
FRAME = "frame"                    # screen frame, base64 JPEG in "data"
INPUT_EVENT = "input_event"
TELEMETRY = "telemetry"
ACTION_REQUEST = "action_request"
ACTION_RESULT = "action_result"
DIAGNOSTIC_REQUEST = "diagnostic_request"
DIAGNOSTIC_REPORT = "diagnostic_report"
SET_VIEW_ONLY = "set_view_only"
DISCONNECT = "disconnect"


def pack(cipher: SessionCipher, msg_type: str, **fields) -> bytes:
    payload = {"type": msg_type, **fields}
    return cipher.encrypt(json.dumps(payload).encode("utf-8"))


def unpack(cipher: SessionCipher, blob: bytes) -> dict:
    return json.loads(cipher.decrypt(blob).decode("utf-8"))
