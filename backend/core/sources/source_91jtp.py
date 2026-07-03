"""91jtp.com：GTP 檔案庫，華語 + 日語曲庫。

⚠️ 查證備註（見任務審計 Step 9）：規格原文的 `/search?wd=` 路徑實測是
301 轉址到不相關的文章頁。實際搜尋表單指向 WordPress 慣用的
`GET https://www.91jtp.com/?s={query}`，但實測這個網站架了滑動驗證
（人機身份驗證）擋自動化請求，直接 GET 只會拿到驗證頁，抓不到真正結果。

這裡用正確的搜尋端點，並用 WordPress 常見的文章列表結構
（article/h2.entry-title a）做保守解析；驗證頁擋下時這些選擇器自然找
不到東西，回傳 None 讓上層靜默跳過，不會誤把驗證頁內容當結果。
"""

from typing import Optional
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from models.schemas import SearchResult

from ._common import polite_get

BASE_URL = "https://www.91jtp.com"


async def search(artist: str, title: str) -> Optional[SearchResult]:
    query = f"{artist} {title}".strip()
    resp = await polite_get(BASE_URL + "/", params={"s": query})
    if resp is None:
        return None

    soup = BeautifulSoup(resp.text, "lxml")
    link = soup.select_one("article h2.entry-title a[href], article .entry-title a[href]")
    if link is None:
        return None

    return SearchResult(
        source="91jtp",
        source_url=urljoin(BASE_URL, link["href"]),
        tab_type="guitar_pro",
        tab_text=None,
        gp_filepath=None,
        chords=[],
        rating=None,
        votes=None,
        score=0.0,
    )
