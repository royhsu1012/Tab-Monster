"""音訊擷取：YouTube URL / MP3 / MP4 / M4A / WAV → 16-bit mono WAV。

安全要求（見任務審計）：
- YouTube URL 僅接受白名單網域，避免 yt-dlp 被當 SSRF 跳板打任意站台
- 上傳檔案僅接受白名單副檔名
- ffmpeg 呼叫一律用 ffmpeg-python 的參數化 API，不用字串拼接組 shell 指令
"""

import uuid
from pathlib import Path
from typing import Optional, Tuple
from urllib.parse import urlparse

import ffmpeg
import soundfile as sf
import yt_dlp

from .errors import TabMonsterError

ALLOWED_YOUTUBE_HOSTS = {
    "youtube.com", "www.youtube.com", "m.youtube.com",
    "music.youtube.com", "youtu.be",
}
ALLOWED_UPLOAD_EXTENSIONS = {".mp3", ".mp4", ".m4a", ".wav"}
MIN_AUDIO_DURATION_SEC = 10.0


def _validate_youtube_url(url: str) -> None:
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        raise TabMonsterError("YOUTUBE_UNAVAILABLE", "不支援的 URL 格式")
    host = (parsed.hostname or "").lower()
    if host not in ALLOWED_YOUTUBE_HOSTS:
        raise TabMonsterError(
            "YOUTUBE_UNAVAILABLE",
            f"僅支援 YouTube 網域，收到: {host or '(空)'}",
        )


def _validate_duration(wav_path: Path) -> float:
    try:
        info = sf.info(str(wav_path))
    except Exception as exc:
        raise TabMonsterError("UNSUPPORTED_FORMAT", "無法讀取音訊檔案") from exc
    duration = info.frames / info.samplerate if info.samplerate else 0.0
    if duration < MIN_AUDIO_DURATION_SEC:
        raise TabMonsterError(
            "AUDIO_TOO_SHORT",
            f"音訊長度僅 {duration:.1f} 秒，需至少 {MIN_AUDIO_DURATION_SEC:.0f} 秒",
        )
    return duration


def extract_from_youtube(url: str, workdir: Path) -> Tuple[Path, dict]:
    """下載 YouTube 音訊並轉成 WAV，回傳 (wav_path, video_metadata)。"""
    _validate_youtube_url(url)
    workdir.mkdir(parents=True, exist_ok=True)
    job_id = uuid.uuid4().hex
    out_template = str(workdir / f"{job_id}.%(ext)s")

    ydl_opts = {
        "format": "bestaudio/best",
        "outtmpl": out_template,
        "postprocessors": [
            {"key": "FFmpegExtractAudio", "preferredcodec": "wav"},
        ],
        "noplaylist": True,
        "quiet": True,
        "no_warnings": True,
        "restrictfilenames": True,
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
    except yt_dlp.utils.DownloadError as exc:
        raise TabMonsterError("YOUTUBE_UNAVAILABLE", str(exc)) from exc

    wav_path = workdir / f"{job_id}.wav"
    if not wav_path.exists():
        raise TabMonsterError("YOUTUBE_UNAVAILABLE", "音訊擷取後找不到輸出檔案")

    _validate_duration(wav_path)
    metadata = {
        "title": info.get("title"),
        "uploader": info.get("uploader"),
        "tags": info.get("tags") or [],
        "duration": info.get("duration"),
    }
    return wav_path, metadata


def extract_from_upload(file_path: Path, original_filename: str, workdir: Path) -> Path:
    """把上傳的 MP3/MP4/M4A/WAV 轉成標準化 WAV（16-bit mono, 44.1kHz）。"""
    ext = Path(original_filename).suffix.lower()
    if ext not in ALLOWED_UPLOAD_EXTENSIONS:
        raise TabMonsterError("UNSUPPORTED_FORMAT", f"不支援的檔案格式: {ext or '(無副檔名)'}")

    workdir.mkdir(parents=True, exist_ok=True)
    wav_path = workdir / f"{uuid.uuid4().hex}.wav"

    try:
        (
            ffmpeg
            .input(str(file_path))
            .output(str(wav_path), ac=1, ar=44100, acodec="pcm_s16le")
            .overwrite_output()
            .run(quiet=True, capture_stdout=True, capture_stderr=True)
        )
    except ffmpeg.Error as exc:
        stderr = exc.stderr.decode("utf-8", errors="ignore") if exc.stderr else str(exc)
        raise TabMonsterError("UNSUPPORTED_FORMAT", f"音訊轉檔失敗: {stderr[:300]}") from exc

    _validate_duration(wav_path)
    return wav_path


def cleanup(*paths: Optional[Path]) -> None:
    """分析完成後立即清除暫存 WAV/GP 檔案。"""
    for path in paths:
        if path is None:
            continue
        try:
            Path(path).unlink(missing_ok=True)
        except OSError:
            pass
