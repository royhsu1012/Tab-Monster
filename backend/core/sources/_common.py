"""7 個 sources/ 模組共用的 HTTP 請求輔助：隨機延遲、User-Agent 輪替、統一逾時/靜默失敗。

集中在這裡而不是每個 source 檔各寫一份，是因為速率限制/UA 輪替是規格明訂的
橫切需求（見任務審計「注意事項 2」），七份重複程式碼只會讓之後調整變成七處要改。
"""

import asyncio
import random
from typing import Optional

import httpx

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4 Safari/605.1.15",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:125.0) Gecko/20100101 Firefox/125.0",
]

SEARCH_TIMEOUT_SEC = 15.0
RATE_DELAY_MIN = 0.5
RATE_DELAY_MAX = 1.5


async def polite_get(
    url: str,
    params: Optional[dict] = None,
    headers: Optional[dict] = None,
) -> Optional[httpx.Response]:
    """隨機延遲 + 隨機 UA 打一個 GET。任何失敗（逾時/連線錯誤/非 200）一律回傳
    None，讓呼叫端可以靜默跳過這個來源，不中斷整體搜尋流程。"""
    await asyncio.sleep(random.uniform(RATE_DELAY_MIN, RATE_DELAY_MAX))
    req_headers = {"User-Agent": random.choice(USER_AGENTS)}
    if headers:
        req_headers.update(headers)
    try:
        async with httpx.AsyncClient(timeout=SEARCH_TIMEOUT_SEC, follow_redirects=True) as client:
            resp = await client.get(url, params=params, headers=req_headers)
            if resp.status_code != 200:
                return None
            return resp
    except httpx.HTTPError:
        return None
