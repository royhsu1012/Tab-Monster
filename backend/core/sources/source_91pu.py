"""91譜（91pu.com.tw）：繁體中文華語曲庫，即時轉調樂譜網站，合法版權。

搜尋端點跟規格原文不同（規格寫 /search/?q=，實測是 404）；用真實請求找到
的是首頁搜尋表單指向的 DedeCMS 搜尋腳本：
GET https://www.91pu.com.tw/plus/search.php?keyword={query}
結果是 server-rendered 的 <table id="songlist">，每列 <tr> 依序是
[歌名連結, 演唱者連結, 作詞, 作曲, 瀏覽次數]。

歌曲詳情頁（/song/...html）本身有和弦六線譜，但實際和弦資料是頁面載入後
用 songID 另外呼叫 AJAX 動態渲染（chord.js），不是嵌在靜態 HTML 裡，所以
這裡只回傳搜尋結果的基本資訊（標題/演出者/連結/瀏覽數當 votes），和弦
清單留空，使用者可以點 source_url 連到 91pu 上看完整可轉調的譜。
"""

from typing import Optional
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from models.schemas import SearchResult

from ._common import polite_get

BASE_URL = "https://www.91pu.com.tw"


async def search(artist: str, title: str) -> Optional[SearchResult]:
    query = f"{artist} {title}".strip()
    resp = await polite_get(f"{BASE_URL}/plus/search.php", params={"keyword": query})
    if resp is None:
        return None

    soup = BeautifulSoup(resp.text, "lxml")
    row = soup.select_one("table#songlist tr, tbody#songlist tr")
    if row is None:
        return None

    cells = row.find_all("td")
    if len(cells) < 5:
        return None

    title_link = cells[0].find("a")
    if title_link is None or not title_link.get("href"):
        return None

    votes: Optional[int] = None
    try:
        votes = int(cells[4].get_text(strip=True))
    except (ValueError, IndexError):
        votes = None

    return SearchResult(
        source="91pu",
        source_url=urljoin(BASE_URL, title_link["href"]),
        tab_type="chords",
        tab_text=None,
        gp_filepath=None,
        chords=[],
        rating=None,
        votes=votes,
        score=0.0,
    )
