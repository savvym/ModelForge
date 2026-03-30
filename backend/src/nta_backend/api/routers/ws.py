from fastapi import APIRouter, WebSocket, WebSocketDisconnect

router = APIRouter(prefix="/ws")


async def _echo_session(websocket: WebSocket, channel: str, session_id: str) -> None:
    await websocket.accept()
    await websocket.send_json(
        {"channel": channel, "session_id": session_id, "message": "connected"}
    )
    try:
        while True:
            message = await websocket.receive_text()
            await websocket.send_json(
                {"channel": channel, "session_id": session_id, "message": message, "echo": True}
            )
    except WebSocketDisconnect:
        await websocket.close()


@router.websocket("/playground/{session_id}")
async def playground_session(websocket: WebSocket, session_id: str) -> None:
    await _echo_session(websocket, "playground", session_id)


@router.websocket("/promptpilot/{session_id}")
async def promptpilot_session(websocket: WebSocket, session_id: str) -> None:
    await _echo_session(websocket, "promptpilot", session_id)
