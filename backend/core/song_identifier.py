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

# YouTube 標題常見的「這是一支什麼影片」描述字詞，會稀釋搜尋相關性。
# 實測過：查 "Hotel California Solo acoustic guitar" 在 Chordie 上會被無關
# 頁面（Emmylou Harris 的另一首歌）搶到最高分，去掉 "Solo acoustic guitar"
# 這類描述字後查 "Hotel California" 才正確命中 Eagles 原曲的和弦頁。
_SEARCH_NOISE_PATTERNS = [
    r"\((?:official|lyrics?|live|cover|hd|4k|audio)[^)]*\)",
    r"\[(?:official|lyrics?|live|cover|hd|4k|audio)[^\]]*\]",
    r"\bofficial\s*(?:music\s*)?video\b", r"\bofficial\s*mv\b", r"\bmv\b",
    r"\b(?:solo\s*)?acoustic\s*(?:guitar\s*)?cover\b", r"\bguitar\s*cover\b", r"\bcover\b",
    r"\bsolo\s*(?:acoustic\s*)?guitar\b", r"\bacoustic\b", r"\bfingerstyle\b",
    r"\bguitar\s*(?:tutorial|lesson)\b", r"\btutorial\b", r"\blesson\b",
    r"\bwith\s*lyrics\b", r"\bkaraoke\b", r"\binstrumental\b", r"\bfull\s*song\b",
    r"（[^）]*(?:伴奏|前奏|教學)[^）]*）", r"\([^)]*(?:伴奏|前奏|教學)[^)]*\)",
    r"純?吉他伴奏", r"吉他教學", r"吉他版", r"彈唱", r"翻彈", r"教學",
    r"^#?[A-G]#?調\s*",
]
_SEARCH_NOISE_RE = re.compile("|".join(_SEARCH_NOISE_PATTERNS), re.IGNORECASE)


def clean_search_title(text: str) -> str:
    """把 YouTube 標題常見的描述字詞（cover/acoustic/官方MV/吉他伴奏...）
    去掉，只留下比較乾淨的歌名去查網路譜庫。只用在搜尋查詢字串，不影響
    SongInfo.title 本身的顯示（顯示保留原始標題，資訊比較完整）。"""
    cleaned = _SEARCH_NOISE_RE.sub(" ", text)
    return re.sub(r"\s+", " ", cleaned).strip()


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
    # 故意不把找不到分隔符時的 uploader（頻道名稱）當成 artist 的 fallback：
    # 翻彈/伴奏影片標題常常沒有「歌手 - 歌名」格式，頻道名稱（例如某個翻彈
    # 頻道）幾乎不會是真正的歌手，拿去查網路譜庫只會查到不相干的結果
    # （實測過："medivet channel - Hotel California" 這樣誤判後，Chordie
    # 搜尋回傳了完全無關的和弦頁面）。artist=None 時 tab_searcher 只會用
    # 標題去搜，反而比硬塞一個錯的歌手名安全。

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
