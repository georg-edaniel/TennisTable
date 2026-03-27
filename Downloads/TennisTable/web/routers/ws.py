"""WebSocket endpoint /ws/live"""
import asyncio
import json
import logging

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Request

from web.core.security import decode_token

logger = logging.getLogger("ws")
router = APIRouter()


@router.websocket("/ws/live")
async def ws_live(websocket: WebSocket):
    # Auth via query param (browser WS constraint)
    token = websocket.query_params.get("token", "")
    user_info = {"role": "guest", "sub": "anon"}
    if token:
        try:
            user_info = decode_token(token)
        except Exception:
            await websocket.close(code=1008)
            return

    ws_manager = websocket.app.state.ws_manager
    await ws_manager.connect(websocket)
    logger.info("WS connected: %s", user_info.get("sub"))

    try:
        while True:
            # Keep-alive: accept ping messages from client
            data = await asyncio.wait_for(websocket.receive_text(), timeout=30)
            msg = json.loads(data)
            if msg.get("type") == "join_session":
                session_id = msg.get("session_id")
                if session_id:
                    await ws_manager.join_room(websocket, int(session_id))
    except (WebSocketDisconnect, asyncio.TimeoutError):
        pass
    except Exception as exc:
        logger.debug("WS error: %s", exc)
    finally:
        await ws_manager.disconnect(websocket)
        logger.info("WS disconnected: %s", user_info.get("sub"))
