"""用 Google Gemini 免費層加強歌曲辨識，取代純 regex 猜測。

刻意設計成「選用」而非必要：整個 TabMonster 預設完全不需要任何付費/需要
API key 的服務就能跑（純 librosa 訊號處理 + 免費爬蟲），這是核心設計原則
（見任務審計）。沒有設定 GEMINI_API_KEY 時，這個模組什麼都不做，直接回傳
core.song_identifier 的 regex-based 結果；設定了才會多打一次 Gemini 呼叫
去修正 regex 猜不準的地方（歌手/歌名順序顛倒、YouTube 頻道名稱誤判成歌手、
標題雜訊字詞——這幾個都是這次真實測試踩到的案例）。呼叫失敗/逾時/回傳格式
不對，一律靜默 fallback 回 regex 版本，不影響整個分析流程能不能跑。
"""

import json
import logging
import os
from typing import Optional

import httpx

from core.song_identifier import identify_from_youtube_metadata
from models.schemas import Genre, Language, SongInfo

logger = logging.getLogger(__name__)

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
GEMINI_MODEL = os.environ.get("GEMINI_MODEL", "gemini-2.0-flash")
GEMINI_URL = f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_MODEL}:generateContent"
GEMINI_TIMEOUT_SEC = 8.0

_VALID_LANGUAGES = {"zh-TW", "zh-CN", "en", "ja", "ko", "other"}
_VALID_GENRES = {"pop", "rock_metal", "indie", "anime_game", "classical", "unknown"}

_RESPONSE_SCHEMA = {
    "type": "object",
    "properties": {
        "artist": {"type": "string", "nullable": True},
        "title": {"type": "string"},
        "language": {"type": "string", "enum": sorted(_VALID_LANGUAGES)},
        "genre": {"type": "string", "enum": sorted(_VALID_GENRES)},
    },
    "required": ["title", "language", "genre"],
}

_PROMPT_TEMPLATE = """你是音樂 metadata 辨識助手。根據 YouTube 影片的標題、上傳頻道名稱、標籤，
判斷這首歌真正的歌手（artist）、歌名（title）、語言（language）、曲風（genre）。

規則：
- title 要去掉「cover」「acoustic」「官方MV」「吉他伴奏」「前奏」「C調」這類
  描述性字詞跟修飾語，只留乾淨的歌名。
- 如果這是翻彈/教學/伴奏影片，上傳頻道通常不是原唱歌手，除非標題裡有明確
  提到原唱歌手，否則 artist 填 null，不要把頻道名稱當成歌手。
- language 只能是這幾種之一：zh-TW, zh-CN, en, ja, ko, other
- genre 只能是這幾種之一：pop, rock_metal, indie, anime_game, classical, unknown
- 只輸出 JSON，不要有其他文字或解釋。

標題: {title}
上傳頻道: {uploader}
標籤: {tags}
"""


async def identify_with_llm(metadata: dict) -> SongInfo:
    fallback = identify_from_youtube_metadata(metadata)
    if not GEMINI_API_KEY:
        return fallback

    prompt = _PROMPT_TEMPLATE.format(
        title=metadata.get("title") or "",
        uploader=metadata.get("uploader") or "",
        tags=", ".join(metadata.get("tags") or []),
    )
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {
            "responseMimeType": "application/json",
            "responseSchema": _RESPONSE_SCHEMA,
            "temperature": 0,
        },
    }

    try:
        async with httpx.AsyncClient(timeout=GEMINI_TIMEOUT_SEC) as client:
            resp = await client.post(GEMINI_URL, params={"key": GEMINI_API_KEY}, json=payload)
            if resp.status_code != 200:
                logger.warning("Gemini identify failed: HTTP %s %s", resp.status_code, resp.text[:200])
                return fallback
            data = resp.json()
            text = data["candidates"][0]["content"]["parts"][0]["text"]
            parsed = json.loads(text)
    except (httpx.HTTPError, KeyError, IndexError, ValueError, json.JSONDecodeError):
        logger.warning("Gemini identify failed, falling back to regex", exc_info=True)
        return fallback

    title = (parsed.get("title") or "").strip() or fallback.title
    artist: Optional[str] = (parsed.get("artist") or "").strip() or None
    language: Language = parsed.get("language") if parsed.get("language") in _VALID_LANGUAGES else fallback.language
    genre: Genre = parsed.get("genre") if parsed.get("genre") in _VALID_GENRES else fallback.genre

    return SongInfo(artist=artist, title=title, language=language, genre=genre, confidence="high")
