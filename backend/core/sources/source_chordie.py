"""Chordie.com：和弦 + 歌詞，來源廣，適合當 fallback。

結構已用真實請求驗證過（見任務審計 Step 9 查證紀錄）：
- 搜尋：GET https://www.chordie.com/results.php?q={query}
- 每筆結果是一個 <div class="... songList">：
  - .rateStar 底下某個 <div> 純文字是評分（0.0~5.0）
  - .songListContent 內第一個 <a> 包兩個 <span>：標題／演出者
  - <span class="label label-default"> 列出和弦，但也混雜 "Fill"、純數字
    這類段落標記（非和弦），需要用簡單的和弦名規則過濾掉
"""

import re
from typing import List, Optional
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from models.schemas import SearchResult

from ._common import polite_get

BASE_URL = "https://www.chordie.com"
_CHORD_TOKEN_RE = re.compile(r"^[A-G](#|b)?(maj|min|dim|aug|sus[24]?|add\d+|m)?\d{0,2}$")


def _looks_like_chord(token: str) -> bool:
    token = token.strip()
    if not token or token.lower() == "fill":
        return False
    return bool(_CHORD_TOKEN_RE.match(token))


async def search(artist: str, title: str) -> Optional[SearchResult]:
    query = f"{artist} {title}".strip()
    resp = await polite_get(f"{BASE_URL}/results.php", params={"q": query})
    if resp is None:
        return None

    soup = BeautifulSoup(resp.text, "lxml")
    item = soup.select_one("div.songList")
    if item is None:
        return None

    link = item.select_one(".songListContent a[href]")
    if link is None or not link.get("href"):
        return None

    rating: Optional[float] = None
    for div in item.select(".rateStar div"):
        text = div.get_text(strip=True)
        try:
            rating = float(text)
            break
        except ValueError:
            continue

    chords: List[str] = []
    for label in item.select("span.label.label-default"):
        text = label.get_text(strip=True)
        if _looks_like_chord(text) and text not in chords:
            chords.append(text)

    return SearchResult(
        source="chordie",
        source_url=urljoin(BASE_URL, link["href"]),
        tab_type="chords",
        tab_text=None,
        gp_filepath=None,
        chords=chords,
        rating=rating,
        votes=None,
        score=0.0,
    )
