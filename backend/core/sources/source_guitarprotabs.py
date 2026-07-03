"""GuitarProTabs.org：Guitar Pro 檔案下載站。

⚠️ 查證備註（見任務審計 Step 9）：實測 `/search.php?search=` 回傳的頁面
只有導覽列跟廣告，沒有任何結果列表或明顯的 AJAX 搜尋呼叫，結果很可能
一樣是靠前端 JS 動態補上（跟 gprotab 情況類似）。做法跟 gprotab 一樣：
保守掃描 .gp 系列副檔名的下載連結，抓不到就回 None，交給上層靜默跳過。
"""

import re
from typing import Optional
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from models.schemas import SearchResult

from ._common import polite_get

BASE_URL = "https://guitarprotabs.org"
GP_FILE_RE = re.compile(r"\.(gp|gp3|gp4|gp5|gpx)$", re.IGNORECASE)


async def search(artist: str, title: str) -> Optional[SearchResult]:
    query = f"{artist} {title}".strip()
    resp = await polite_get(f"{BASE_URL}/search.php", params={"search": query})
    if resp is None:
        return None

    soup = BeautifulSoup(resp.text, "lxml")
    link = next(
        (a for a in soup.find_all("a", href=True) if GP_FILE_RE.search(a["href"])),
        None,
    )
    if link is None:
        return None

    return SearchResult(
        source="guitarprotabs",
        source_url=urljoin(BASE_URL, link["href"]),
        tab_type="guitar_pro",
        tab_text=None,
        gp_filepath=None,
        chords=[],
        rating=None,
        votes=None,
        score=0.0,
    )
