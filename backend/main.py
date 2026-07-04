"""Step 13：FastAPI SSE endpoints。"""

import asyncio
import os
import uuid
from pathlib import Path
from typing import AsyncGenerator, Callable

from fastapi import FastAPI, File, HTTPException, Query, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse

from core import audio_extractor, pipeline, song_identifier
from core.errors import TabMonsterError
from models.schemas import ProgressEvent

MAX_UPLOAD_SIZE_MB = int(os.environ.get("MAX_UPLOAD_SIZE_MB", "100"))
UPLOAD_DIR = Path(os.environ.get("UPLOAD_DIR", "./.tmp_uploads"))
DEFAULT_MODE = os.environ.get("DEFAULT_MODE", "parallel")
VALID_MODES = {"web_first", "ai_only", "parallel"}

app = FastAPI(title="TabMonster API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    # 個人/本機使用先開放所有來源；對外公開部署前應改成只允許前端網域
    allow_origins=["*"],
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)


def _validate_mode(mode: str) -> str:
    if mode not in VALID_MODES:
        raise HTTPException(status_code=400, detail=f"invalid mode: {mode}, must be one of {sorted(VALID_MODES)}")
    return mode


async def _stream_pipeline(
    coro_factory: Callable[[Callable], "asyncio.Future"],
) -> AsyncGenerator[str, None]:
    """把 pipeline.run() 的 progress_cb 風格橋接成 SSE async generator：
    背景跑實際分析工作，進度事件經 queue 轉發給前端，錯誤轉成 step="error" 事件。"""
    queue: "asyncio.Queue[object]" = asyncio.Queue()
    sentinel = object()

    async def progress_cb(step: str, message: str, data: dict = None) -> None:
        await queue.put(ProgressEvent(step=step, message=message, data=data))

    async def runner() -> None:
        try:
            await coro_factory(progress_cb)
        except TabMonsterError as exc:
            await queue.put(ProgressEvent(step="error", message=exc.message, data={"code": exc.code}))
        except Exception as exc:  # noqa: BLE001 - 任何未預期例外都要回報成 SSE 錯誤事件，不能讓連線卡死
            await queue.put(ProgressEvent(step="error", message=str(exc), data={"code": "ANALYSIS_FAILED"}))
        finally:
            await queue.put(sentinel)

    task = asyncio.create_task(runner())
    try:
        while True:
            item = await queue.get()
            if item is sentinel:
                break
            yield f"data: {item.model_dump_json()}\n\n"
    finally:
        if not task.done():
            task.cancel()


@app.get("/api/health")
async def health():
    return {"status": "ok", "version": "1.0.0"}


@app.get("/api/analyze/stream")
async def analyze_stream(url: str = Query(...), mode: str = Query(DEFAULT_MODE), song_hint: str = Query("")):
    mode = _validate_mode(mode)
    job_id = uuid.uuid4().hex
    workdir = UPLOAD_DIR / job_id

    async def pipeline_coro(progress_cb):
        await progress_cb("extract", "下載並擷取音訊中...")
        wav_path, metadata = await asyncio.to_thread(audio_extractor.extract_from_youtube, url, workdir)
        await progress_cb("extract", "音訊擷取完成")

        song = song_identifier.identify_from_youtube_metadata(metadata)
        if song_hint.strip():
            song = song_identifier.apply_manual_hint(song, song_hint)
        await progress_cb(
            "identify",
            f"辨識歌曲: {song.artist or '?'} - {song.title or '?'} ({song.language}/{song.genre})",
            {"song": song.model_dump()},
        )
        try:
            await pipeline.run(song, wav_path, mode, workdir, progress_cb)
        finally:
            audio_extractor.cleanup(wav_path)

    return StreamingResponse(_stream_pipeline(pipeline_coro), media_type="text/event-stream")


@app.post("/api/analyze/file/stream")
async def analyze_file_stream(
    mode: str = Query(DEFAULT_MODE),
    song_hint: str = Query(""),
    file: UploadFile = File(...),
):
    mode = _validate_mode(mode)
    job_id = uuid.uuid4().hex
    workdir = UPLOAD_DIR / job_id
    workdir.mkdir(parents=True, exist_ok=True)

    raw = await file.read()
    if len(raw) > MAX_UPLOAD_SIZE_MB * 1024 * 1024:
        raise HTTPException(status_code=413, detail=f"file exceeds {MAX_UPLOAD_SIZE_MB}MB limit")

    original_filename = file.filename or "upload"
    upload_path = workdir / f"{uuid.uuid4().hex}_{Path(original_filename).name}"
    upload_path.write_bytes(raw)

    async def pipeline_coro(progress_cb):
        # 先從原始上傳檔讀 ID3 metadata，再轉檔——轉完 WAV 就沒有 tag 資訊可讀了
        song = song_identifier.identify_from_file_metadata(upload_path)
        if song_hint.strip():
            song = song_identifier.apply_manual_hint(song, song_hint)
        await progress_cb(
            "identify",
            f"辨識歌曲: {song.artist or '?'} - {song.title or '?'} ({song.language}/{song.genre})",
            {"song": song.model_dump()},
        )
        await progress_cb("extract", "轉換音訊中...")
        try:
            wav_path = await asyncio.to_thread(
                audio_extractor.extract_from_upload, upload_path, original_filename, workdir
            )
        finally:
            upload_path.unlink(missing_ok=True)
        await progress_cb("extract", "音訊轉換完成")

        try:
            await pipeline.run(song, wav_path, mode, workdir, progress_cb)
        finally:
            audio_extractor.cleanup(wav_path)

    return StreamingResponse(_stream_pipeline(pipeline_coro), media_type="text/event-stream")
