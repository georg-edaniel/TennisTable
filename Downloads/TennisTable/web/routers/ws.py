"""WebSocket endpoint /ws/live"""
import asyncio
import json
import logging

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from web.core.security import decode_token

logger = logging.getLogger("ws")
router = APIRouter()

ACCESS_COOKIE = "access_token"

# Byte → stroke key (matches Arduino firmware classes)
_STROKE_MAP = {
    0: "bh_drive",
    1: "bh_smash",
    2: "fh_drive",
    3: "fh_loop",
    4: "fh_smash",
}
_STROKE_LABELS = {
    "bh_drive": "BH Drive",
    "bh_smash": "BH Smash",
    "fh_drive": "FH Drive",
    "fh_loop":  "FH Loop",
    "fh_smash": "FH Smash",
}


async def _handle_ble_stroke(msg: dict, user_info: dict, session_id: int | None, ws_manager):
    """Process a ble_stroke message sent from the browser (Web Bluetooth)."""
    stroke_id = msg.get("stroke_id")
    device = msg.get("device", "WebBLE")

    stroke_key = _STROKE_MAP.get(stroke_id)
    if stroke_key is None:
        return  # ignore idle (5) or unknown bytes

    label = _STROKE_LABELS[stroke_key]
    payload = {
        "device": device,
        "player_id": user_info.get("sub"),
        "last_stroke": {"id": stroke_id, "name": label, "key": stroke_key},
        "source": "web_bluetooth",
    }
    event = {"type": "stroke", "data": payload}

    # Broadcast only to the session room (scoped, not all clients)
    if session_id:
        await ws_manager.broadcast_room(session_id, event)
    else:
        # No active session — broadcast only back to this connection (solo practice)
        pass

    # Record in DB if a session is active
    if session_id:
        try:
            from web.core.database import db_context
            from web.services.session_service import record_stroke_increment
            with db_context() as db:
                record_stroke_increment(db, int(session_id), stroke_key)
        except Exception as exc:
            logger.debug("BLE stroke record error: %s", exc)


@router.websocket("/ws/live")
async def ws_live(websocket: WebSocket):
    # Auth via HttpOnly cookie (same-origin — browser sends cookies automatically)
    token = websocket.cookies.get(ACCESS_COOKIE, "")
    user_info: dict = {"role": "guest", "sub": "anon"}

    if token:
        try:
            user_info = decode_token(token)
            # Reject guest tokens from sensitive operations (still allow connect for live view)
            if user_info.get("role") == "guest":
                user_info["sub"] = "guest"
        except Exception:
            await websocket.close(code=1008, reason="Token invalide")
            return
    # Anonymous users allowed for live spectating (read-only); write ops checked below

    ws_manager = websocket.app.state.ws_manager
    await ws_manager.connect(websocket)
    logger.info("WS connected: %s", user_info.get("sub"))

    current_session_id: int | None = None

    try:
        while True:
            data = await asyncio.wait_for(websocket.receive_text(), timeout=60)
            try:
                msg = json.loads(data)
            except json.JSONDecodeError:
                continue

            msg_type = msg.get("type")

            if msg_type == "join_session":
                sid = msg.get("session_id")
                if sid and str(sid).isdigit():
                    current_session_id = int(sid)
                    await ws_manager.join_room(websocket, current_session_id)

            elif msg_type == "ble_stroke":
                # Require authenticated user for write operations
                if user_info.get("sub") in ("anon", "guest"):
                    continue
                sid = msg.get("session_id") or current_session_id
                await _handle_ble_stroke(msg, user_info, int(sid) if sid else None, ws_manager)

            elif msg_type == "ping":
                await websocket.send_text(json.dumps({"type": "pong"}))

    except (WebSocketDisconnect, asyncio.TimeoutError):
        pass
    except Exception as exc:
        logger.debug("WS error: %s", exc)
    finally:
        await ws_manager.disconnect(websocket)
        logger.info("WS disconnected: %s", user_info.get("sub"))
