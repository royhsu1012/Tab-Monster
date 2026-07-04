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
from core.capo_detector import suggest_capo, transpose_chord, transpose_key_label
from core.gp_parser import parse_gp_file
from core.tab_generator import notes_to_ascii
from models.schemas import ChordEvent, ChordInfo, Measure, SearchResult, SongInfo, StrumEvent, TabMonsterResult, TabResult
from utils.chord_templates import CHORD_DATA

logger = logging.getLogger(__name__)

CHORD_SPACING_SEC = 4.0
BEATS_PER_MEASURE = 4
SUBDIVISIONS_PER_BEAT = 2


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


def build_measures(
    beat_times: List[float],
    chords: List[ChordEvent],
    strums: List[StrumEvent],
) -> List[Measure]:
    """把拍子網格切成小節（假設 4/4 拍——這個專案不偵測拍號，4/4 是流行/搖滾
    最常見的情況），每個小節標上開頭該彈的和弦，跟每個 8 分音符格子的刷弦方向。

    小節的「第一拍」是抓拍演算法偵測到的第一個拍子，不一定是這首歌真正的
    小節起點（真正對齊小節起點需要 downbeat 偵測，這個專案沒做），但小節
    長度跟間隔是準的，至少給一個穩定、可讀的分組方式，比攤平的時間軸好讀。
    """
    if len(beat_times) < BEATS_PER_MEASURE + 1:
        return []

    num_measures = (len(beat_times) - 1) // BEATS_PER_MEASURE
    num_slots = BEATS_PER_MEASURE * SUBDIVISIONS_PER_BEAT

    measures: List[Measure] = []
    chord_idx = 0
    for m in range(num_measures):
        beat_start_idx = m * BEATS_PER_MEASURE
        start_time = beat_times[beat_start_idx]
        end_time = beat_times[beat_start_idx + BEATS_PER_MEASURE]

        while chord_idx + 1 < len(chords) and chords[chord_idx + 1].time <= start_time:
            chord_idx += 1
        chord = chords[chord_idx].chord if chords else None

        slot_duration = (end_time - start_time) / num_slots
        slots: List[Optional[str]] = [None] * num_slots
        for s in strums:
            if start_time <= s.time < end_time:
                slot_idx = min(int((s.time - start_time) / slot_duration), num_slots - 1)
                slots[slot_idx] = s.direction

        measures.append(Measure(index=m, start_time=start_time, chord=chord, strums=slots))

    return measures


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
    strum_pattern: Optional[List[StrumEvent]] = None,
    beat_times: Optional[List[float]] = None,
    all_web_results: Optional[List[TabResult]] = None,
    sources_tried: Optional[List[str]] = None,
    warnings: Optional[List[str]] = None,
) -> TabMonsterResult:
    warnings = list(warnings or [])

    # 和弦偵測是照實際物理音高比對，capo 夾在哪都會被正確偵測成「實際發出的音」
    # （例如 F#、C# 這種吉他手很少真的這樣彈的調）。這裡額外推論一個建議 capo
    # 位置，如果有，就把和弦/調性換算成「夾 capo 後應該彈的簡單和弦」顯示，
    # 對使用者比較有用；偵測邏輯本身（chroma 比對）完全不受影響。
    capo = suggest_capo([c.chord for c in chords])
    if capo:
        chords = [
            ChordEvent(time=c.time, chord=transpose_chord(c.chord, capo) or c.chord)
            for c in chords
        ]
        key = transpose_key_label(key, capo)
        warnings.append(f"偵測到和弦可能是夾 Capo {capo} 彈奏，和弦/調性已換算成夾 capo 後的簡單版本顯示")

    chord_names = [c.chord for c in chords]
    strum_pattern = strum_pattern or []
    measures = build_measures(beat_times or [], chords, strum_pattern)
    return TabMonsterResult(
        song=song,
        bpm=bpm or 0.0,
        key=key,
        mode_used=mode_used,
        primary_tab=primary_tab,
        secondary_tab=secondary_tab,
        chords=chords,
        chord_info=build_chord_info(chord_names),
        strum_pattern=strum_pattern,
        measures=measures,
        suggested_capo=capo,
        all_web_results=all_web_results or [],
        sources_tried=sources_tried or [],
        status="ok",
        warnings=warnings,
    )
