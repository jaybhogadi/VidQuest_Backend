
from __future__ import annotations

import asyncio
import json
import os
import re
import uuid
from collections import defaultdict
from dataclasses import dataclass
from typing import Any, Dict, List, Optional
import asyncio
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
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from dataclasses import dataclass, field
from contextlib import asynccontextmanager

from services.whisper_service import whisper_service
from services.llm_service import llm_service
from Models.data_models import VideoUploadRequest
from utils.settings import settings
from utils.log_details import logger
from utils.websocket_manager import manager
from services.pipeline import _pipeline


# Lifespan function using @asynccontextmanager
@asynccontextmanager
async def lifespan_fun(app: FastAPI):
    # Startup logic
    try:
        logger.info("Starting up the application...")
        await whisper_service.ensure_model()
        await llm_service.ensure_llm()
        logger.info("Models loaded successfully.")
    except Exception as e:
        logger.warning("Startup failed; will retry on demand", exc_info=True)

    yield  # The application runs here
    # Shutdown logic
    try:
        logger.info("Shutting down the application...")
        # Add any cleanup logic here if needed
    except Exception as e:
        logger.error("Shutdown failed", exc_info=True)

# --------- FastAPI App ---------
app = FastAPI(title="Video → MCQ API",lifespan=lifespan_fun)


app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --------- REST Endpoints ---------
@app.post("/upload-file")
async def upload_file(file: UploadFile = File(...), requestId: str = Form(...)):
    """Upload a video file directly. Returns a path_name to process next."""
    if not requestId:
        raise HTTPException(status_code=400, detail="requestId is required")

    # Generate unique filename with original ext if present
    ext = os.path.splitext(file.filename or "")[1] or ".mp4"
    safe_name = f"video-{uuid.uuid4()}{ext}"
    file_path = os.path.join(settings.UPLOAD_DIR, safe_name)

    try:
        contents = await file.read()
        with open(file_path, "wb") as f:
            f.write(contents)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error saving file: {e}")

    return {
        "status": "success",
        "message": "File uploaded",
        "path_name": safe_name,
        "requestId": requestId,
    }

@app.post("/process")
async def process_video(req: VideoUploadRequest, background: BackgroundTasks):
    """Process an already-uploaded video file: transcribe → generate MCQs.
    Progress + result are pushed over WebSocket (by requestId)."""
    try:
        file_path = os.path.join(settings.UPLOAD_DIR, req.path_name)
        if not os.path.exists(file_path):
            # help debugging: list what we do have
            existing = []
            try:
                existing = os.listdir(settings.UPLOAD_DIR)
            except Exception as e:
                logger.error("exception is e",e)
                pass
            raise HTTPException(status_code=404, detail={"msg": "File not found", "have": existing})

        # Kick off background pipeline
        background.add_task(_pipeline, req.requestId, file_path, int(req.num_questions))
        return {"status": "accepted", "requestId": req.requestId}
    except Exception as e:
        logger.error("Exception is",e)

@app.get("/health")
async def health():
    return {"status": "ok"}

# --------- WebSocket ---------
@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    request_id = ws.query_params.get("requestId")
    if not request_id:
        await ws.close(code=1008)
        return

    await manager.connect(ws, request_id)
    try:
        # optional: receive pings/commands from client
        while True:
            _ = await ws.receive_text()
            # simple echo or ignore
    except WebSocketDisconnect:
        manager.disconnect(ws, request_id)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("run:app", host="127.0.0.1", port=8000, reload=True)
