"""Step 12：三種分析模式（web_first / ai_only / parallel）總調度，
透過 progress_cb 回呼推送 SSE 進度事件。

SONG_UNIDENTIFIABLE 設計為軟性警告而非硬性錯誤：辨識不到歌名時就跳過
網路搜譜（沒有關鍵字可查），但 AI 分析不需要歌名也能跑，所以不因此中斷
整個流程 —— 只有網路搜譜和 AI 分析「同時」失敗時才視為致命錯誤
（ALL_SOURCES_FAILED / ANALYSIS_FAILED）。
"""

import asyncio
import logging
from pathlib import Path
from typing import Awaitable, Callable, List, Optional, Tuple

from core import audio_analyzer, result_merger, tab_generator, tab_searcher
from core.audio_analyzer import AudioAnalysisResult
from core.errors import TabMonsterError
from models.schemas import SearchResult, SongInfo, TabMonsterResult, TabResult

logger = logging.getLogger(__name__)

ProgressCallback = Callable[[str, str, Optional[dict]], Awaitable[None]]
WEB_FIRST_HIGH_SCORE_THRESHOLD = 60.0


async def _emit(progress_cb: Optional[ProgressCallback], step: str, message: str, data: Optional[dict] = None) -> None:
    if progress_cb:
        await progress_cb(step, message, data)


async def _run_ai_analysis(
    wav_path: Path, progress_cb: Optional[ProgressCallback]
) -> Tuple[AudioAnalysisResult, TabResult]:
    await _emit(progress_cb, "ai:hpss", "分離人聲/伴奏與打擊樂...")
    # librosa 是同步、CPU 密集的呼叫，丟到執行緒池跑，
    # 這樣 parallel 模式下才能真的跟網路搜尋同時進行，不會卡住 event loop
    analysis = await asyncio.to_thread(audio_analyzer.analyze, str(wav_path))
    await _emit(progress_cb, "ai:pitch", f"偵測到 {len(analysis.pitches)} 個音符")
    await _emit(progress_cb, "ai:chords", f"偵測到 {len(analysis.chords)} 個和弦變化")
    await _emit(progress_cb, "ai:bpm", f"BPM ≈ {analysis.bpm:.0f}")
    await _emit(progress_cb, "generate:midi", "產生 MIDI...")
    ai_tab = tab_generator.generate_tab(analysis.pitches, analysis.bpm)
    await _emit(progress_cb, "generate:tab", "產生六線譜完成")
    return analysis, ai_tab


async def _build_all_web_tabs(
    results: List[SearchResult], primary_tab: TabResult, workdir: Path
) -> List[TabResult]:
    """組「切換來源」清單：第一筆重用已經解析好的 primary_tab（避免重複下載），
    guitar_pro 類型的其餘結果不逐一下載（太貴），只留連結；其他類型直接轉換
    （便宜，沒有下載成本）。"""
    tabs = [primary_tab]
    for r in results[1:]:
        if r.tab_type == "guitar_pro":
            tabs.append(TabResult(
                ascii="(Guitar Pro 檔案，點擊來源連結查看/下載)",
                notes=[], tab_type=r.tab_type, source=r.source,
                source_url=r.source_url, rating=r.rating, score=r.score,
            ))
            continue
        resolved = await result_merger.resolve_web_tab(r, workdir)
        if resolved is not None:
            tabs.append(resolved[0])
        else:
            tabs.append(TabResult(
                ascii="(暫時無法讀取，點擊來源連結查看)",
                notes=[], tab_type=r.tab_type, source=r.source,
                source_url=r.source_url, rating=r.rating, score=r.score,
            ))
    return tabs


async def run(
    song: SongInfo,
    wav_path: Path,
    mode: str,
    workdir: Path,
    progress_cb: Optional[ProgressCallback] = None,
) -> TabMonsterResult:
    if mode == "ai_only":
        return await _run_ai_only(song, wav_path, progress_cb)
    if mode == "web_first":
        return await _run_web_first(song, wav_path, workdir, progress_cb)
    if mode == "parallel":
        return await _run_parallel(song, wav_path, workdir, progress_cb)
    raise ValueError(f"unknown mode: {mode}")


async def _run_ai_only(song: SongInfo, wav_path: Path, progress_cb) -> TabMonsterResult:
    analysis, ai_tab = await _run_ai_analysis(wav_path, progress_cb)
    if not analysis.pitches and not analysis.chords:
        raise TabMonsterError("ANALYSIS_FAILED", "AI 分析沒有偵測到任何音高或和弦")

    result = result_merger.assemble(
        song=song, mode_used="ai_only", primary_tab=ai_tab,
        chords=analysis.chords, bpm=analysis.bpm, key=analysis.key,
    )
    await _emit(progress_cb, "done", "完成", {"result": result.model_dump()})
    return result


async def _run_web_first(song: SongInfo, wav_path: Path, workdir: Path, progress_cb) -> TabMonsterResult:
    warnings: List[str] = []
    sources = tab_searcher.get_sources(song.language, song.genre)
    await _emit(progress_cb, "route", f"選定來源: {', '.join(sources) or '(無，直接 AI 分析)'}", {"sources": sources})

    web_results: List[SearchResult] = []
    if sources and song.title:
        await _emit(progress_cb, "search", f"搜尋 {len(sources)} 個來源...")
        web_results = await tab_searcher.search_sources(sources, song)
        for r in web_results:
            await _emit(progress_cb, f"search:{r.source}", f"{r.source} 找到結果，分數 {r.score:.0f}")
    elif sources and not song.title:
        warnings.append("歌曲標題無法辨識，略過網路搜譜")

    if web_results and web_results[0].score >= WEB_FIRST_HIGH_SCORE_THRESHOLD:
        resolved = await result_merger.resolve_web_tab(web_results[0], workdir)
        if resolved is not None:
            web_tab, meta, gp_warnings = resolved
            warnings.extend(gp_warnings)
            await _emit(progress_cb, "ai_chords", "網路譜品質足夠，AI 只補和弦時間軸...")
            analysis = await asyncio.to_thread(audio_analyzer.analyze, str(wav_path))
            chords = analysis.chords or result_merger.chords_from_names(meta.get("chords") or [])
            all_web_tabs = await _build_all_web_tabs(web_results, web_tab, workdir)
            result = result_merger.assemble(
                song=song, mode_used="web_first", primary_tab=web_tab,
                chords=chords, bpm=analysis.bpm or meta.get("bpm") or 0.0,
                key=analysis.key or meta.get("key"),
                all_web_results=all_web_tabs, sources_tried=sources, warnings=warnings,
            )
            await _emit(progress_cb, "done", "完成", {"result": result.model_dump()})
            return result
        warnings.append(f"最高分網路譜（{web_results[0].source}）下載/解析失敗，改用完整 AI 分析比對")

    if web_results:
        await _emit(progress_cb, "ai_full", "網路譜分數不夠高，AI 完整分析做對比...")
        analysis, ai_tab = await _run_ai_analysis(wav_path, progress_cb)
        resolved = await result_merger.resolve_web_tab(web_results[0], workdir)
        if resolved is not None:
            web_tab, meta, gp_warnings = resolved
            warnings.extend(gp_warnings)
            all_web_tabs = await _build_all_web_tabs(web_results, web_tab, workdir)
            result = result_merger.assemble(
                song=song, mode_used="web_first_both", primary_tab=web_tab, secondary_tab=ai_tab,
                chords=analysis.chords, bpm=analysis.bpm, key=analysis.key,
                all_web_results=all_web_tabs, sources_tried=sources, warnings=warnings,
            )
        else:
            warnings.append("網路譜下載/解析失敗，改用 AI 譜當主譜")
            result = result_merger.assemble(
                song=song, mode_used="ai_fallback", primary_tab=ai_tab,
                chords=analysis.chords, bpm=analysis.bpm, key=analysis.key,
                sources_tried=sources, warnings=warnings,
            )
        await _emit(progress_cb, "done", "完成", {"result": result.model_dump()})
        return result

    await _emit(progress_cb, "fallback", "找不到網路譜，改用 AI 分析")
    analysis, ai_tab = await _run_ai_analysis(wav_path, progress_cb)
    if not analysis.pitches and not analysis.chords:
        code = "ALL_SOURCES_FAILED" if sources else "ANALYSIS_FAILED"
        raise TabMonsterError(code, "網路搜譜與 AI 分析都沒有得到可用結果")

    result = result_merger.assemble(
        song=song, mode_used="ai_fallback", primary_tab=ai_tab,
        chords=analysis.chords, bpm=analysis.bpm, key=analysis.key,
        sources_tried=sources, warnings=warnings,
    )
    await _emit(progress_cb, "done", "完成", {"result": result.model_dump()})
    return result


async def _run_parallel(song: SongInfo, wav_path: Path, workdir: Path, progress_cb) -> TabMonsterResult:
    warnings: List[str] = []
    sources = tab_searcher.get_sources(song.language, song.genre)
    await _emit(progress_cb, "route", f"選定來源: {', '.join(sources) or '(無)'}", {"sources": sources})

    async def _web_task() -> List[SearchResult]:
        if not sources or not song.title:
            return []
        return await tab_searcher.search_sources(sources, song)

    await _emit(progress_cb, "search", "並行搜尋網路譜 + AI 分析中...")
    # return_exceptions=True：任一邊整個掛掉也不能拖垮另一邊（見任務審計）
    gathered = await asyncio.gather(
        _web_task(), _run_ai_analysis(wav_path, progress_cb), return_exceptions=True
    )
    web_results, ai_pack = gathered

    if isinstance(web_results, BaseException):
        logger.warning("parallel mode: web search raised", exc_info=web_results)
        web_results = []
    if isinstance(ai_pack, BaseException):
        logger.warning("parallel mode: AI analysis raised", exc_info=ai_pack)
        ai_pack = None

    if not web_results and ai_pack is None:
        raise TabMonsterError("ALL_SOURCES_FAILED", "網路搜譜與 AI 分析都失敗")

    analysis, ai_tab = ai_pack if ai_pack is not None else (None, None)

    web_tab: Optional[TabResult] = None
    meta: dict = {}
    if web_results:
        resolved = await result_merger.resolve_web_tab(web_results[0], workdir)
        if resolved is not None:
            web_tab, meta, gp_warnings = resolved
            warnings.extend(gp_warnings)
        else:
            warnings.append(f"最高分網路譜（{web_results[0].source}）下載/解析失敗")

    if web_tab is not None and ai_tab is not None:
        all_web_tabs = await _build_all_web_tabs(web_results, web_tab, workdir)
        result = result_merger.assemble(
            song=song, mode_used="parallel", primary_tab=web_tab, secondary_tab=ai_tab,
            chords=analysis.chords, bpm=analysis.bpm, key=analysis.key,
            all_web_results=all_web_tabs, sources_tried=sources, warnings=warnings,
        )
    elif web_tab is not None:
        all_web_tabs = await _build_all_web_tabs(web_results, web_tab, workdir)
        result = result_merger.assemble(
            song=song, mode_used="parallel_web_only", primary_tab=web_tab,
            chords=result_merger.chords_from_names(meta.get("chords") or []),
            bpm=meta.get("bpm") or 0.0, key=meta.get("key"),
            all_web_results=all_web_tabs, sources_tried=sources, warnings=warnings,
        )
    else:
        result = result_merger.assemble(
            song=song, mode_used="parallel_ai_fallback", primary_tab=ai_tab,
            chords=analysis.chords, bpm=analysis.bpm, key=analysis.key,
            sources_tried=sources, warnings=warnings,
        )

    await _emit(progress_cb, "done", "完成", {"result": result.model_dump()})
    return result
