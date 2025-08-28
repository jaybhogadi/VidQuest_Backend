from utils.log_details import logger
from utils.websocket_manager import push_progress,manager

from services.llm_service import llm_service
from services.whisper_service import whisper_service

# --------- Pipeline ---------
async def _pipeline(request_id: str, file_path: str, n: int) -> None:
    try:
        await push_progress(request_id, "queued", 0, "Job accepted")

        await push_progress(request_id, "transcribe", 10, "Loading model")
        transcript = ""
        async for ev in whisper_service.stream_segments(
            file_path, language="en", beam_size=5, without_timestamps=False
        ):
            if ev["type"] == "segment":
                # push incremental transcript to the UI
                await manager.send_json(request_id, {
                    "type": "partial",
                    "requestId": request_id,
                    "stage": "transcribe",
                    "pct": ev["pct"],
                    "segment": ev["segment"],   # {id,start,end,text}
                })
            elif ev["type"] == "done":
                transcript = ev["transcript"]
                await push_progress(request_id, "transcribe", 100, "Transcript ready")
        # tr = await whisper_service.transcribe(file_path)
        # print("transcript is tr",tr)
        # tr=await whisper_service.transcribe(audio=file_path, language="en", beam_size=5,log_progress=True)
        # transcript = tr.get("transcript", "").strip()
        if not transcript:
            raise RuntimeError("Empty transcript")
        # await push_progress(request_id, "transcribe", 60, "Transcript ready")

        await push_progress(request_id, "generate", 70, "Generating MCQs")
        mcqs = await llm_service.generate_mcqs(transcript, n)
        await push_progress(request_id, "generate", 95, "MCQs ready")

        # Ship result
        await manager.send_json(
            request_id,
            {
                "type": "result",
                "requestId": request_id,
                "mcqs": [m.model_dump() for m in mcqs],
                "transcript": transcript,
            },
        )
        await push_progress(request_id, "done", 100, "Completed")
    except Exception as e:
        logger.error("Pipeline failed", exc_info=e)
        await manager.send_json(
            request_id,
            {
                "type": "error",
                "requestId": request_id,
                "error": str(e),
            },
        )