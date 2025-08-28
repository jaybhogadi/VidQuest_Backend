from __future__ import annotations
import logging
from collections import defaultdict
from dataclasses import dataclass
from typing import Any, Dict, List, Optional
import asyncio
from typing import AsyncIterator, Dict, Any

from fastapi import (
    BackgroundTasks,
    FastAPI,
    File,
    Form,
    HTTPException,
    Request,
    UploadFile,
    WebSocket,
    WebSocketDisconnect,
)

# --------- Logging ---------
logging.basicConfig(level=logging.INFO, format="[%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("video-mcq")

class ConnectionManager:
    def __init__(self) -> None:
        self._by_request: Dict[str, set[WebSocket]] = defaultdict(set)

    async def connect(self, websocket: WebSocket, request_id: str) -> None:
        await websocket.accept()
        self._by_request[request_id].add(websocket)
        logger.info(f"WS connected: requestId={request_id}, total={len(self._by_request[request_id])}")

    def disconnect(self, websocket: WebSocket, request_id: str) -> None:
        if request_id in self._by_request and websocket in self._by_request[request_id]:
            self._by_request[request_id].remove(websocket)
            if not self._by_request[request_id]:
                self._by_request.pop(request_id, None)
        logger.info(f"WS disconnected: requestId={request_id}")

    async def send_json(self, request_id: str, payload: Dict[str, Any]) -> None:
        conns = list(self._by_request.get(request_id, []))
        for ws in conns:
            try:
                await ws.send_json(payload)
            except Exception:
                # drop broken connections
                self.disconnect(ws, request_id)
                
manager = ConnectionManager()

async def push_progress(request_id: str, stage: str, pct: int, msg: str = "") -> None:
    st={"type": "progress", "requestId": request_id, "stage": stage, "pct": pct, "msg": msg}
    await manager.send_json(
        request_id,
        {"type": "progress", "requestId": request_id, "stage": stage, "pct": pct, "msg": msg},
    )
                

