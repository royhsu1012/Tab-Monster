"""Songsterr：多軌完整譜（節奏 + 吉他/貝斯/鼓分軌），適合英語搖滾/金屬。

已用真實請求驗證過（見任務審計 Step 9 查證紀錄）：
- 舊版規格寫的 /a/ra/songs.json 端點已經 404，實際可用的是
  GET https://www.songsterr.com/api/songs?pattern={query}
  回傳 JSON array，每首歌有 songId/artist/title/hasChords/tracks[]
- 詳細譜面本身是 Songsterr 專有格式，沒有直接下載連結，所以 tab_type 用
  "full_tab"（不是 guitar_pro），tab_text 留空，只帶 source_url 讓使用者
  自己去網站上看
- 歌曲頁面網址格式為 /a/wsa/{任意 slug}-tab-s{songId}，slug 內容不影響
  路由（已實測用不精確的 slug 也能正確導到該首歌），song_id 才是真正的 key
"""

import re
from typing import Optional

from models.schemas import SearchResult

from ._common import polite_get

API_URL = "https://www.songsterr.com/api/songs"


def _slugify(text: str) -> str:
    text = re.sub(r"[^a-zA-Z0-9]+", "-", text.strip().lower())
    return re.sub(r"-{2,}", "-", text).strip("-") or "tab"


async def search(artist: str, title: str) -> Optional[SearchResult]:
    query = f"{artist} {title}".strip()
    resp = await polite_get(API_URL, params={"pattern": query})
    if resp is None:
        return None

    try:
        songs = resp.json()
    except ValueError:
        return None
    if not songs:
        return None

    song = songs[0]
    song_id = song.get("songId")
    song_title = song.get("title") or title
    song_artist = song.get("artist") or artist
    if song_id is None:
        return None

    slug = _slugify(f"{song_artist}-{song_title}")
    source_url = f"https://www.songsterr.com/a/wsa/{slug}-tab-s{song_id}"

    tracks = song.get("tracks") or []
    votes = sum(int(t.get("views") or 0) for t in tracks) or None

    return SearchResult(
        source="songsterr",
        source_url=source_url,
        tab_type="full_tab",
        tab_text=None,
        gp_filepath=None,
        chords=[],
        rating=None,
        votes=votes,
        score=0.0,
    )
