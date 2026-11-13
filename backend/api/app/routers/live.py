"""WebSocket /ws/live (api-contracts.md §4): the server pushes events, the client only listens."""
from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from ..realtime import CLOSE

router = APIRouter(tags=["live"])


@router.websocket("/ws/live")
async def live(websocket: WebSocket) -> None:
    hub = websocket.app.state.hub
    await websocket.accept()
    queue = hub.register()
    try:
        while True:
            event = await queue.get()
            if event is CLOSE:
                await websocket.close(code=1013)      # "try again later": this client fell too far behind
                break
            await websocket.send_json(event)
    except (WebSocketDisconnect, RuntimeError):
        pass                                          # browser went away
    finally:
        hub.unregister(queue)