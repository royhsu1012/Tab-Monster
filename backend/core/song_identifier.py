"""歌曲辨識：從 YouTube metadata 或上傳檔案 ID3 tag 猜 artist/title/language/genre。

已知限制（見任務審計）：
1. 沒有維護台灣/香港/大陸藝人名單資料來源，中文語言判斷僅依字元寫法
   （簡體字/繁體字集合）區分 zh-CN / zh-TW，無法用藝人身分輔助判斷。
2. 純漢字、無假名的日文標題（例如「前前前世」）若 tags 也沒有假名線索，
   會被誤判為中文，此為字元集判斷法的固有限制。
"""

import re
from pathlib import Path
from typing import List, Optional, Tuple

from models.schemas import Confidence, Genre, Language, SongInfo

HIRAGANA_KATAKANA = re.compile(r"[぀-ヿ]")
HANGUL = re.compile(r"[가-힯ᄀ-ᇿ]")
CJK = re.compile(r"[一-鿿]")

# 常見簡體/繁體專用字元（同一詞的兩種寫法），用來粗略區分 zh-CN / zh-TW
SIMPLIFIED_ONLY = set("爱国学习这对说话时间没关系机场经济历史点亲进达远")
TRADITIONAL_ONLY = set("愛國學習這對說話時間沒關係機場經濟歷史點親進達遠")

ROCK_METAL_KEYWORDS = ["metal", "rock", "punk", "hardcore", "thrash", "死亡金屬", "搖滾"]
ANIME_GAME_KEYWORDS = ["ost", "bgm", "op主題曲", "ed主題曲", "動畫", "动画", "アニメ", "game", "遊戲", "游戏"]
CLASSICAL_KEYWORDS = ["jazz", "classical", "fingerstyle", "古典", "爵士"]
INDIE_KEYWORDS = ["indie", "獨立製作", "独立制作", "demo"]

ARTIST_TITLE_SEPS = [" - ", "－", "–", "—", "｜", " | ", "：", ": "]


def _detect_language(text: str) -> Language:
    if HANGUL.search(text):
        return "ko"
    if HIRAGANA_KATAKANA.search(text):
        return "ja"
    if CJK.search(text):
        simplified_hits = sum(1 for ch in text if ch in SIMPLIFIED_ONLY)
        traditional_hits = sum(1 for ch in text if ch in TRADITIONAL_ONLY)
        return "zh-CN" if simplified_hits > traditional_hits else "zh-TW"
    if text.strip():
        return "en"
    return "other"


def _detect_genre(text: str, tags: List[str]) -> Genre:
    haystack = (text + " " + " ".join(tags)).lower()
    if any(k in haystack for k in ROCK_METAL_KEYWORDS):
        return "rock_metal"
    if any(k in haystack for k in ANIME_GAME_KEYWORDS):
        return "anime_game"
    if any(k in haystack for k in CLASSICAL_KEYWORDS):
        return "classical"
    if any(k in haystack for k in INDIE_KEYWORDS):
        return "indie"
    return "pop"


def _split_artist_title(raw: str) -> Tuple[Optional[str], Optional[str]]:
    for sep in ARTIST_TITLE_SEPS:
        if sep in raw:
            artist, _, title = raw.partition(sep)
            artist, title = artist.strip(), title.strip()
            if artist and title:
                return artist, title
    stripped = raw.strip()
    return None, (stripped or None)


def identify_from_youtube_metadata(metadata: dict) -> SongInfo:
    raw_title = metadata.get("title") or ""
    tags = metadata.get("tags") or []
    artist, title = _split_artist_title(raw_title)
    if artist is None and metadata.get("uploader"):
        artist = metadata["uploader"]

    # 純漢字的日文標題（例如「前前前世」）沒有假名可判斷語言，
    # 但 tags 常帶假名（如「アニメ」），一併納入可大幅降低誤判成中文的機率
    language = _detect_language(raw_title + " " + " ".join(tags))
    genre = _detect_genre(raw_title, tags)
    confidence: Confidence = "high" if (artist and title) else ("medium" if title else "low")
    return SongInfo(artist=artist, title=title, language=language, genre=genre, confidence=confidence)


def identify_from_file_metadata(file_path: Path) -> SongInfo:
    from mutagen import File as MutagenFile

    artist: Optional[str] = None
    title: Optional[str] = None
    try:
        audio = MutagenFile(str(file_path), easy=True)
        if audio:
            artist = (audio.get("artist") or [None])[0]
            title = (audio.get("title") or [None])[0]
    except Exception:
        pass

    if not title:
        stem = Path(file_path).stem
        parsed_artist, parsed_title = _split_artist_title(stem)
        artist = artist or parsed_artist
        title = title or parsed_title or stem

    text_for_lang = f"{artist or ''} {title or ''}"
    language = _detect_language(text_for_lang)
    genre = _detect_genre(text_for_lang, [])
    confidence: Confidence = "high" if (artist and title) else ("medium" if title else "low")
    return SongInfo(artist=artist, title=title, language=language, genre=genre, confidence=confidence)
