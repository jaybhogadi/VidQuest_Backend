import asyncio
from utils.settings import settings
from utils.log_details import logger
from utils.threadpool_exxecutor import EXECUTOR
from typing import List
from typing import AsyncIterator, Dict, Any


# --------- Whisper Service ---------
class WhisperService:
    def __init__(self) -> None:
        self._model = None
        self._lock = asyncio.Lock()

    def _initialize_sync(self) -> None:
        from faster_whisper import WhisperModel

        logger.info(
            f"Initializing Whisper model: {settings.WHISPER_MODEL} on {settings.WHISPER_DEVICE}"
        )
        self._model = WhisperModel(
            settings.WHISPER_MODEL,
            device=settings.WHISPER_DEVICE,
            compute_type="int8",
        )
        logger.info("Whisper model initialized")
        
    
    async def stream_segments(self, file_path: str, *, language="en",
                              beam_size: int = 5,
                              without_timestamps: bool = False,
                              word_timestamps: bool = False) -> AsyncIterator[Dict[str, Any]]:
        """
        Async generator that yields {'type': 'segment', 'segment': {...}, 'pct': int}
        and finally {'type': 'done', 'info': {...}, 'transcript': '...'}.
        """
        await self.ensure_model()
        loop = asyncio.get_running_loop()
        q: asyncio.Queue = asyncio.Queue()
        SENTINEL = object()
        pieces: list[str] = []

        def worker():
            try:
                # this is the Faster-Whisper call that returns (segments_generator, info)
                segments, info = self._model.transcribe(
                    file_path,
                    language=language,
                    beam_size=beam_size,
                    without_timestamps=without_timestamps,
                    word_timestamps=word_timestamps,
                )
                total = max(info.duration, 1e-6)

                for seg in segments:  # <-- streaming from the model
                    payload = {
                        "id": seg.id,
                        "start": float(seg.start),
                        "end": float(seg.end),
                        "text": seg.text,
                    }
                    pieces.append(seg.text.strip())
                    pct = int(min(95, (seg.end / total) * 100))
                    loop.call_soon_threadsafe(q.put_nowait, ("segment", payload, pct))

                final = {
                    "language": info.language,
                    "duration": float(info.duration),
                    "duration_after_vad": float(info.duration_after_vad),
                }
                transcript = " ".join(t for t in pieces if t).strip()
                loop.call_soon_threadsafe(q.put_nowait, ("done", final, transcript))
            except Exception as e:
                loop.call_soon_threadsafe(q.put_nowait, ("error", str(e), None))
            finally:
                loop.call_soon_threadsafe(q.put_nowait, (SENTINEL, None, None))

        EXECUTOR.submit(worker)

        while True:
            kind, payload, extra = await q.get()
            if kind is SENTINEL:
                break
            if kind == "segment":
                yield {"type": "segment", "segment": payload, "pct": extra}
            elif kind == "done":
                yield {"type": "done", "info": payload, "transcript": extra}
            elif kind == "error":
                raise RuntimeError(extra)

    async def ensure_model(self) -> None:
        if self._model is None:
            async with self._lock:
                if self._model is None:
                    loop = asyncio.get_running_loop()
                    await loop.run_in_executor(EXECUTOR, self._initialize_sync)

    def _transcribe_sync(self, file_path: str) -> Dict[str, Any]:
        try:
            assert self._model is not None, "Whisper model not initialized"
            segments, info = self._model.transcribe(
                audio=file_path,
                language="en", beam_size=5,log_progress=True
                # vad_filter=True,
                # vad_parameters=dict(min_silence_duration_ms=500),
            )
            texts: List[str] = []
            for seg in segments:  # `segments` is a generator
                texts.append(seg.text.strip())
            transcript = " ".join(t for t in texts if t)
            return {"language": getattr(info, "language", None), "transcript": transcript}
        except Exception as e:
            print("exception in ensuring model",e)

    async def transcribe(self, file_path: str) -> Dict[str, Any]:
        await self.ensure_model()
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(EXECUTOR, self._transcribe_sync, file_path)

whisper_service = WhisperService()