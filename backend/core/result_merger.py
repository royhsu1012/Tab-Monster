"""Step 11：把異質的搜尋結果/AI 分析結果，合併成最終的 TabMonsterResult。

分工原則：這裡只負責「資料轉換 + 組裝」，哪種模式該用哪個組合（例如網路
譜分數夠不夠高、要不要跑 AI 補和弦）是 pipeline.py 的職責，避免同一個
決策邏輯分散在兩個檔案裡。
"""

import logging
import uuid
from pathlib import Path
from typing import List, Optional, Tuple

import httpx

from core.audio_analyzer import AudioAnalysisResult
from core.gp_parser import parse_gp_file
from core.tab_generator import notes_to_ascii
from models.schemas import ChordEvent, ChordInfo, SearchResult, SongInfo, TabMonsterResult, TabResult
from utils.chord_templates import CHORD_DATA

logger = logging.getLogger(__name__)

CHORD_SPACING_SEC = 4.0


async def _download(url: str, workdir: Path) -> Optional[Path]:
    workdir.mkdir(parents=True, exist_ok=True)
    dest = workdir / f"{uuid.uuid4().hex}.gp"
    try:
        async with httpx.AsyncClient(timeout=15.0, follow_redirects=True) as client:
            resp = await client.get(url)
            if resp.status_code != 200:
                return None
            dest.write_bytes(resp.content)
            return dest
    except httpx.HTTPError:
        return None


def chords_from_names(names: List[str]) -> List[ChordEvent]:
    """網路譜通常只給和弦名稱清單、沒有精確時間點，用等間隔排一個粗略時間軸
    （比完全沒有時間軸好，讓 ChordTimeline 至少能畫出順序）。"""
    return [ChordEvent(time=i * CHORD_SPACING_SEC, chord=name) for i, name in enumerate(names)]


def build_chord_info(chord_names: List[str]) -> List[ChordInfo]:
    seen: List[str] = []
    infos: List[ChordInfo] = []
    for name in chord_names:
        if name in seen or name not in CHORD_DATA:
            continue
        seen.append(name)
        data = CHORD_DATA[name]
        infos.append(ChordInfo(chord=name, fingering=data["fingering"], barre_fret=data["barre_fret"]))
    return infos


async def resolve_web_tab(result: SearchResult, workdir: Path) -> Optional[Tuple[TabResult, dict, List[str]]]:
    """把一個 SearchResult 轉成 (TabResult, {bpm,key,chords}, warnings)。
    下載/解析失敗回傳 None，由呼叫端決定要不要換下一個候選來源。"""
    if result.tab_type == "guitar_pro":
        gp_path = await _download(result.source_url, workdir)
        if gp_path is None:
            return None
        try:
            tab_result, meta, warnings = parse_gp_file(str(gp_path), source=result.source, source_url=result.source_url)
        except Exception:
            logger.warning("failed to parse GP file from %s", result.source, exc_info=True)
            return None
        finally:
            gp_path.unlink(missing_ok=True)
        tab_result.rating = result.rating
        tab_result.score = result.score
        return tab_result, meta, warnings

    # full_tab / chords：沒有逐音符資料，用和弦清單組一個簡易顯示
    ascii_text = result.tab_text or (" - ".join(result.chords) if result.chords else "(no detailed tab, see source_url)")
    tab_result = TabResult(
        ascii=ascii_text,
        notes=[],
        tab_type=result.tab_type,
        source=result.source,
        source_url=result.source_url,
        rating=result.rating,
        score=result.score,
    )
    meta = {"bpm": None, "key": None, "chords": result.chords}
    return tab_result, meta, []


def assemble(
    song: SongInfo,
    mode_used: str,
    primary_tab: TabResult,
    chords: List[ChordEvent],
    secondary_tab: Optional[TabResult] = None,
    bpm: Optional[float] = None,
    key: Optional[str] = None,
    all_web_results: Optional[List[TabResult]] = None,
    sources_tried: Optional[List[str]] = None,
    warnings: Optional[List[str]] = None,
) -> TabMonsterResult:
    chord_names = [c.chord for c in chords]
    return TabMonsterResult(
        song=song,
        bpm=bpm or 0.0,
        key=key,
        mode_used=mode_used,
        primary_tab=primary_tab,
        secondary_tab=secondary_tab,
        chords=chords,
        chord_info=build_chord_info(chord_names),
        all_web_results=all_web_results or [],
        sources_tried=sources_tried or [],
        status="ok",
        warnings=warnings or [],
    )
