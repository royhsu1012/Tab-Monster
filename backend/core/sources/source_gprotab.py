"""GProTab.net：70K+ Guitar Pro 檔案，英語為主，免登入直接下載。

⚠️ 查證備註（見任務審計 Step 9）：實測 `/en/search/?s=` 這個端點回傳的是
一個空殼頁面（jQuery + page-loader），結果內容不在初始 HTML 裡，也沒在
common.js 找到對應的搜尋 AJAX 呼叫，代表這個搜尋頁很可能是需要瀏覽器
執行 JS 才會補上結果，用單純 httpx GET 抓不到。

這裡still依規格實作 GET 請求 + 保守的連結掃描（找 .gp/.gp3/.gp4/.gp5
下載連結），如果之後這個端點行為改變（變成 server-rendered，或找到真正
的 API）會直接生效；短期內預期大部分查詢會回傳 None，這是設計上允許的
「靜默跳過」，不是 bug。
"""

import re
from typing import Optional
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from models.schemas import SearchResult

from ._common import polite_get

BASE_URL = "https://gprotab.net"
GP_FILE_RE = re.compile(r"\.(gp|gp3|gp4|gp5|gpx)$", re.IGNORECASE)


async def search(artist: str, title: str) -> Optional[SearchResult]:
    query = f"{artist} {title}".strip()
    resp = await polite_get(f"{BASE_URL}/en/search/", params={"s": query})
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
        source="gprotab",
        source_url=urljoin(BASE_URL, link["href"]),
        tab_type="guitar_pro",
        tab_text=None,
        gp_filepath=None,
        chords=[],
        rating=None,
        votes=None,
        score=0.0,
    )
