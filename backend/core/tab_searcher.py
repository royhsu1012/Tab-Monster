"""Step 10：依語言/類型路由到對應來源，平行搜尋 + 評分排序。"""

import asyncio
import logging
from typing import Dict, List, Tuple

from models.schemas import SearchResult, SongInfo
from core.song_identifier import clean_search_title
from core.sources import (
    source_91jtp,
    source_91pu,
    source_chordie,
    source_gprotab,
    source_guitarprotabs,
    source_songsterr,
    source_ultimate_guitar,
)

logger = logging.getLogger(__name__)

SOURCE_ROUTING: Dict[object, List[str]] = {
    ("zh-TW", "pop"): ["91pu", "91jtp", "ultimate_guitar", "chordie"],
    ("zh-CN", "pop"): ["91jtp", "91pu", "ultimate_guitar", "chordie"],
    ("en", "pop"): ["gprotab", "guitarprotabs", "songsterr", "ultimate_guitar", "chordie"],
    ("en", "rock_metal"): ["songsterr", "gprotab", "guitarprotabs", "ultimate_guitar"],
    ("ja", "pop"): ["gprotab", "ultimate_guitar"],
    ("*", "anime_game"): ["gprotab", "guitarprotabs", "ultimate_guitar"],
    ("ko", "*"): [],
    ("other", "*"): [],
    "default": ["gprotab", "ultimate_guitar", "chordie"],
}

SOURCE_REGISTRY = {
    "91pu": source_91pu.search,
    "91jtp": source_91jtp.search,
    "gprotab": source_gprotab.search,
    "guitarprotabs": source_guitarprotabs.search,
    "songsterr": source_songsterr.search,
    "ultimate_guitar": source_ultimate_guitar.search,
    "chordie": source_chordie.search,
}

_SCORE_BASE = {"guitar_pro": 100, "full_tab": 60, "chords": 20}


def get_sources(language: str, genre: str) -> List[str]:
    key: Tuple[str, str] = (language, genre)
    if key in SOURCE_ROUTING:
        return SOURCE_ROUTING[key]
    key = (language, "*")
    if key in SOURCE_ROUTING:
        return SOURCE_ROUTING[key]
    key = ("*", genre)
    if key in SOURCE_ROUTING:
        return SOURCE_ROUTING[key]
    return SOURCE_ROUTING["default"]


def score_result(result: SearchResult) -> float:
    score = _SCORE_BASE.get(result.tab_type, 0)
    if result.rating:
        score += result.rating * 5
    if result.votes:
        score += min(result.votes / 100, 20)
    return score


async def search_sources(source_names: List[str], song: SongInfo) -> List[SearchResult]:
    """依名單平行呼叫各來源，任一來源例外或逾時都靜默跳過，不影響其他來源。"""
    artist = song.artist or ""
    title = clean_search_title(song.title or "")

    async def _run_one(name: str):
        fn = SOURCE_REGISTRY.get(name)
        if fn is None:
            return None
        try:
            return await fn(artist, title)
        except Exception:
            logger.warning("source %s failed, skipping silently", name, exc_info=True)
            return None

    raw_results = await asyncio.gather(*(_run_one(name) for name in source_names))

    results: List[SearchResult] = []
    for r in raw_results:
        if r is None:
            continue
        r.score = score_result(r)
        results.append(r)

    results.sort(key=lambda r: r.score, reverse=True)
    return results
