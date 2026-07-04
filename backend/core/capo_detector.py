"""Capo 位置推論：把偵測到的和弦序列往下移調 0~7 品，挑「開放和弦比例」最高的
那個位移當建議 capo。

「開放和弦」的定義直接複用 utils/chord_templates.py 裡已經人工驗證過的指法資料
（barre_fret is None），不另外維護一份「好彈和弦」白名單 —— 這樣 Step 3 驗證過的
和弦資料跟這裡的判斷永遠一致，改一個地方兩邊都會更新。

背景：AI 和弦偵測是照實際物理音高比對 chroma，capo 夾在哪都一樣會被正確偵測成
「實際發出的音」（例如 F#、C# 這種對吉他手來說難彈的調）。但真人彈奏時通常會夾
capo 用簡單的開放和弦形狀（E、A、D、G、C）演奏，所以「絕對音高正確」不等於
「呈現方式對使用者有用」，這個模組就是把兩者對上。
"""

import re
from typing import List, Optional, Tuple

from utils.chord_templates import CHORD_DATA, NOTE_INDEX

MAX_CAPO = 7
# capo>0 的開放和弦比例至少要比 capo=0 高這麼多，才值得建議
# （避免對本來就已經很簡單的和弦進行硬加 capo）
MIN_IMPROVEMENT = 0.15
# 就算某個 capo 位移「相對最佳」，比例太低也不該硬推薦（可能整首歌本來就用很多barre/爵士和弦）
MIN_ABSOLUTE_SCORE = 0.5
# 分數差在這個範圍內視為「差不多、雜訊等級」，不能只挑單一最高分——
# 實測過一首真實錄音，capo=2 跟 capo=4 的開放和弦比例只差 0.026（0.692 vs
# 0.718），但這首歌實際上是 capo 2，選到分數「嚴格最高」的 4 反而錯了。
# 低把位 capo（1~3）在現實中遠比高把位常見，證據沒有壓倒性差距時，
# 在同樣「差不多好」的候選裡優先選最低的 capo，比死板選最高分更貼近實際情況。
TIE_BREAK_MARGIN = 0.05

NOTE_NAMES = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]
OPEN_CHORD_NAMES = {name for name, data in CHORD_DATA.items() if data["barre_fret"] is None}

_ROOT_RE = re.compile(r"^([A-Ga-g])(#|b)?(.*)$")


def _split_root(chord_name: str) -> Optional[Tuple[str, str]]:
    """把和弦名稱拆成 (根音, 剩下的性質字串)。認不出根音就回傳 None
    （例如 slash chord "G/B"、奇怪的縮寫），呼叫端要能安全跳過。"""
    match = _ROOT_RE.match(chord_name)
    if not match:
        return None
    letter, accidental, quality = match.groups()
    root_key = letter.upper() + (accidental or "")
    if root_key not in NOTE_INDEX:
        return None
    return NOTE_NAMES[NOTE_INDEX[root_key]], quality


def transpose_root(root: str, semitones: int) -> Optional[str]:
    if root not in NOTE_INDEX:
        return None
    new_idx = (NOTE_INDEX[root] - semitones) % 12
    return NOTE_NAMES[new_idx]


def transpose_chord(chord_name: str, semitones: int) -> Optional[str]:
    """把和弦名稱往下移調 semitones 個半音（capo N 品彈出的實際音高，
    等於原本形狀往下移 N 個半音）。認不出的和弦名稱回傳 None。"""
    if semitones == 0:
        return chord_name
    parsed = _split_root(chord_name)
    if parsed is None:
        return None
    root, quality = parsed
    new_root = transpose_root(root, semitones)
    return f"{new_root}{quality}" if new_root else None


def transpose_key_label(key: Optional[str], semitones: int) -> Optional[str]:
    """跟 transpose_chord 一樣，但處理 audio_analyzer/gp_parser 產生的
    'F# major' / 'C minor' 這種帶空格的 key 字串格式。"""
    if not key or semitones == 0:
        return key
    parts = key.split(" ", 1)
    if len(parts) != 2:
        return key
    root, quality = parts
    new_root = transpose_root(root, semitones)
    return f"{new_root} {quality}" if new_root else key


def _open_ratio(chord_names: List[str], capo: int) -> Optional[float]:
    parseable = 0
    open_count = 0
    for name in chord_names:
        transposed = transpose_chord(name, capo)
        if transposed is None:
            continue
        parseable += 1
        if transposed in OPEN_CHORD_NAMES:
            open_count += 1
    if parseable == 0:
        return None
    return open_count / parseable


def suggest_capo(chord_names: List[str]) -> int:
    """回傳建議的 capo 位置，0 代表不建議加 capo（含資料不足以判斷的情況）。"""
    if not chord_names:
        return 0

    scores = {0: _open_ratio(chord_names, 0) or 0.0}
    for capo in range(1, MAX_CAPO + 1):
        score = _open_ratio(chord_names, capo)
        if score is not None:
            scores[capo] = score

    base_score = scores[0]
    best_score = max(scores.values())

    if best_score < MIN_ABSOLUTE_SCORE:
        return 0
    if best_score - base_score < MIN_IMPROVEMENT:
        return 0

    # 分數在 best_score 附近（差距 <= TIE_BREAK_MARGIN）的候選裡選最低的 capo
    tied_candidates = [c for c, s in scores.items() if c > 0 and best_score - s <= TIE_BREAK_MARGIN]
    return min(tied_candidates) if tied_candidates else 0
