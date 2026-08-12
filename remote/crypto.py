"""Session-code based AES-256-GCM encryption.

The session code is the *only* secret. It is generated locally by the host,
shown to the user (and out-of-band shared with the technician), and never
sent to the relay server on its own -- the relay only ever sees the derived
room id and opaque ciphertext.

Room id and encryption key are both derived from the code via HKDF with
different `info` labels, so knowing the room id (which the relay does see)
does not reveal the key.
"""

import base64
import os
import secrets

from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

_CODE_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"  # no 0/O/1/I ambiguity


def generate_session_code(length=8):
    return "".join(secrets.choice(_CODE_ALPHABET) for _ in range(length))


def _hkdf(code: str, info: bytes, length=32) -> bytes:
    return HKDF(
        algorithm=hashes.SHA256(),
        length=length,
        salt=b"pc-cleaner-remote-assist",
        info=info,
    ).derive(code.encode("utf-8"))


def room_id_for_code(code: str) -> str:
    return base64.urlsafe_b64encode(_hkdf(code, b"room-id", 16)).decode("ascii").rstrip("=")


def key_for_code(code: str) -> bytes:
    return _hkdf(code, b"aead-key", 32)


class SessionCipher:
    """Encrypts/decrypts JSON-serializable envelopes for one session."""

    def __init__(self, code: str):
        self.key = key_for_code(code)
        self._aead = AESGCM(self.key)

    def encrypt(self, plaintext: bytes) -> bytes:
        nonce = os.urandom(12)
        return nonce + self._aead.encrypt(nonce, plaintext, None)

    def decrypt(self, blob: bytes) -> bytes:
        nonce, ct = blob[:12], blob[12:]
        return self._aead.decrypt(nonce, ct, None)
