"""WebSocket routes for event streaming."""
from fastapi import APIRouter, WebSocket
from ..streaming.websocket import handle_websocket_stream

router = APIRouter(tags=["websocket"])


@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """
    WebSocket endpoint for real-time event streaming.

    Clients connect to this endpoint to receive events as they are published.
    The connection includes:
    - Automatic ping/pong keepalive (every 30 seconds)
    - Rate limiting (100 messages per 60 seconds)
    - Automatic reconnection handling

    Example client (JavaScript):
    ```javascript
    const ws = new WebSocket('ws://localhost:8080/ws');
    ws.onmessage = (event) => {
        const data = JSON.parse(event.data);
        console.log('Received:', data);
        if (data.type === 'ping') {
            ws.send('pong');
        }
    };
    ```
    """
    await handle_websocket_stream(websocket)
