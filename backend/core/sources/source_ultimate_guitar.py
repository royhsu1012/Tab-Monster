"""Ultimate Guitar：最大的譜庫，但有明確的反爬蟲機制。

⚠️ 查證備註（見任務審計 Step 9）：實測直接 GET search.php 會被擋下回
403（Cloudflare 等級的防護，不是單純 UA 檢查）。這裡依規格文件描述的
做法實作（頁面內嵌 JSON `window.UGAPP.store.page.data`），如果之後
403 狀況緩解（例如換到允許存取的環境/IP）程式碼可以直接生效；目前預期
這個來源在大多數情況下會直接靜默失敗，這也是為什麼路由表把它放在
候選清單後段而不是第一順位。
"""

import json
import re
from typing import Optional

from models.schemas import SearchResult

from ._common import polite_get

BASE_URL = "https://www.ultimate-guitar.com"
_STORE_DATA_RE = re.compile(
    r"window\.UGAPP\.store\.page\s*=\s*(\{.*?\});\s*(?:</script>|\n)",
    re.DOTALL,
)


async def search(artist: str, title: str) -> Optional[SearchResult]:
    query = f"{artist} {title}".strip()
    resp = await polite_get(
        f"{BASE_URL}/search.php",
        params={"search_type": "title", "value": query},
    )
    if resp is None:
        return None

    match = _STORE_DATA_RE.search(resp.text)
    if match is None:
        return None

    try:
        page_data = json.loads(match.group(1))
        results = page_data["data"]["results"]
    except (ValueError, KeyError, TypeError):
        return None

    tab_result = next((r for r in results if r.get("type") == "Tab"), None) or (
        results[0] if results else None
    )
    if tab_result is None:
        return None

    tab_url = tab_result.get("tab_url")
    if not tab_url:
        return None

    rating = tab_result.get("rating")
    votes = tab_result.get("votes")
    tab_type_raw = (tab_result.get("type_name") or "").lower()
    tab_type = "guitar_pro" if "pro" in tab_type_raw or "tab" in tab_type_raw else "chords"

    return SearchResult(
        source="ultimate_guitar",
        source_url=tab_url,
        tab_type=tab_type,
        tab_text=None,
        gp_filepath=None,
        chords=[],
        rating=float(rating) if rating is not None else None,
        votes=int(votes) if votes is not None else None,
        score=0.0,
    )
