"""Thin WebSocket relay for remote-assistance sessions.

Forwards opaque encrypted frames between exactly two peers that connect
with the same room id. Never decrypts, inspects, or logs frame contents.
Rooms are dropped when either peer disconnects, or after being unclaimed
(only one peer joined) for ROOM_UNCLAIMED_TIMEOUT seconds.

Run standalone:
    python -m remote.relay_server [--host 0.0.0.0] [--port 8765]

This is meant to be run by whoever operates the relay (the user, on
localhost/LAN or their own server) -- it is not bundled as a public cloud
service.
"""

import argparse
import asyncio
import logging
import time

import websockets

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("relay")

ROOM_UNCLAIMED_TIMEOUT = 600  # seconds
MAX_ROOM_SIZE = 2

_rooms: dict[str, list] = {}
_room_created_at: dict[str, float] = {}


async def _reap_stale_rooms():
    while True:
        await asyncio.sleep(30)
        now = time.time()
        stale = [
            room_id
            for room_id, peers in _rooms.items()
            if len(peers) < MAX_ROOM_SIZE and now - _room_created_at.get(room_id, now) > ROOM_UNCLAIMED_TIMEOUT
        ]
        for room_id in stale:
            for ws in _rooms.pop(room_id, []):
                await ws.close(code=4000, reason="session expired")
            _room_created_at.pop(room_id, None)
            log.info("reaped stale room %s", room_id)


async def handler(websocket):
    room_id = None
    try:
        path = websocket.request.path if hasattr(websocket, "request") else websocket.path
        room_id = path.strip("/").split("/")[-1]
        if not room_id:
            await websocket.close(code=4001, reason="missing room id")
            return

        peers = _rooms.setdefault(room_id, [])
        _room_created_at.setdefault(room_id, time.time())
        if len(peers) >= MAX_ROOM_SIZE:
            await websocket.close(code=4002, reason="room full")
            return
        peers.append(websocket)
        log.info("peer joined room %s (%d/%d)", room_id, len(peers), MAX_ROOM_SIZE)

        async for message in websocket:
            for peer in list(_rooms.get(room_id, [])):
                if peer is not websocket:
                    await peer.send(message)
    except websockets.exceptions.ConnectionClosed:
        pass
    finally:
        if room_id and room_id in _rooms:
            peers = _rooms[room_id]
            if websocket in peers:
                peers.remove(websocket)
            for peer in peers:
                await peer.close(code=4003, reason="peer disconnected")
            _rooms.pop(room_id, None)
            _room_created_at.pop(room_id, None)
            log.info("room %s closed", room_id)


async def main():
    parser = argparse.ArgumentParser(description="PC Cleaner remote-assistance relay")
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args()

    async with websockets.serve(handler, args.host, args.port, max_size=4 * 1024 * 1024):
        log.info("relay listening on %s:%d", args.host, args.port)
        await _reap_stale_rooms()


if __name__ == "__main__":
    asyncio.run(main())
