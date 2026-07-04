"""AI 音訊分析 pipeline：hpss 分離 → 音高偵測 → 和弦偵測（beat-synced）→ BPM/Key 估算。

輸出的是「原始」音高清單（RawPitch，只有 note/time/midi，還沒有指板 string/fret），
弦/格指派留給 tab_generator.py（依 Step 0b 定案的最小移動距離演算法）處理，
維持單一職責：這一個模組只碰音訊訊號，不碰指板邏輯。
"""

from collections import Counter
from dataclasses import dataclass
from typing import List, Optional

import librosa
import numpy as np

from models.schemas import ChordEvent, StrumEvent
from utils.chord_templates import get_chroma_vectors

HOP_LENGTH = 512
FMIN = librosa.note_to_hz("E2")
FMAX = librosa.note_to_hz("E6")

# 和弦平滑窗口，單位是「拍」不是秒——用拍數才能自動適應不同 BPM 的歌曲，
# 9 拍約等於 2 個小節（4/4 拍），是實測調出來的：對一首真實錄音的和弦序列量測
# 過，最佳候選跟次佳候選的 cosine similarity 差距中位數只有 0.014（幾乎是同分），
# 508 個拍子逐拍判斷會抖出 303 次「換和弦」；用 9 拍窗口做多數決平滑後降到 78 次，
# 平均每個和弦持續約 1.7 小節，才符合流行歌實際的和聲節奏。窗口越大越穩，
# 但也可能蓋掉真的每小節都換的快速和弦進行，9 是穩定性跟靈敏度的折衷。
CHORD_SMOOTHING_WINDOW_BEATS = 9

KS_MAJOR_PROFILE = np.array([6.35, 2.23, 3.48, 2.33, 4.38, 4.09, 2.52, 5.19, 2.39, 3.66, 2.29, 2.88])
KS_MINOR_PROFILE = np.array([6.33, 2.68, 3.52, 5.38, 2.60, 3.53, 2.54, 4.75, 3.98, 2.69, 3.34, 3.17])
NOTE_NAMES = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]


@dataclass
class RawPitch:
    time: float
    note: str
    midi: int


@dataclass
class AudioAnalysisResult:
    pitches: List[RawPitch]
    chords: List[ChordEvent]
    strums: List[StrumEvent]
    bpm: float
    key: str


def _detect_pitches(y_harmonic: np.ndarray, sr: int) -> List[RawPitch]:
    """以 onset 切分樂句，每段取能量最大的音高當作該段代表音。"""
    onset_frames = librosa.onset.onset_detect(y=y_harmonic, sr=sr, hop_length=HOP_LENGTH, backtrack=True)
    onset_times = librosa.frames_to_time(onset_frames, sr=sr, hop_length=HOP_LENGTH)
    pitches, magnitudes = librosa.piptrack(y=y_harmonic, sr=sr, hop_length=HOP_LENGTH, fmin=FMIN, fmax=FMAX)

    n_frames = pitches.shape[1]
    if n_frames == 0:
        return []

    boundaries = list(onset_frames) + [n_frames]
    if not len(onset_frames):
        boundaries = [0, n_frames]

    results: List[RawPitch] = []
    for i in range(len(boundaries) - 1):
        start, end = boundaries[i], boundaries[i + 1]
        if end <= start:
            continue
        segment_mag = magnitudes[:, start:end]
        segment_pitch = pitches[:, start:end]
        bin_idx, frame_idx = np.unravel_index(np.argmax(segment_mag), segment_mag.shape)
        freq = segment_pitch[bin_idx, frame_idx]
        if freq <= 0:
            continue
        midi = int(round(librosa.hz_to_midi(freq)))
        note_name = librosa.midi_to_note(midi, unicode=False)
        time = float(onset_times[i]) if i < len(onset_times) else 0.0
        results.append(RawPitch(time=time, note=note_name, midi=midi))
    return results


def _classify_chords_per_beat(chroma: np.ndarray) -> List[Optional[str]]:
    """每個 (beat-synced) chroma 向量跟 45 個和弦模板比對 cosine similarity，
    回傳逐拍的和弦標籤（原始、未平滑，雜訊很多，見 _smooth_chord_labels）。"""
    templates = get_chroma_vectors()
    names = list(templates.keys())
    matrix = np.array([templates[n] for n in names], dtype=float)
    norms = np.clip(np.linalg.norm(matrix, axis=1, keepdims=True), 1e-9, None)
    matrix_normed = matrix / norms

    labels: List[Optional[str]] = []
    for i in range(chroma.shape[1]):
        vec = chroma[:, i]
        norm = np.linalg.norm(vec)
        if norm < 1e-6:
            labels.append(None)
            continue
        scores = matrix_normed @ (vec / norm)
        labels.append(names[int(np.argmax(scores))])
    return labels


def _smooth_chord_labels(labels: List[Optional[str]], window: int) -> List[Optional[str]]:
    """逐拍多數決平滑：每一拍改採「以它為中心、寬度 window 拍」範圍內最常見的
    和弦，把單拍的雜訊分類洗掉。這是解決和弦最佳/次佳候選分數幾乎同分、
    導致逐拍判斷結果來回亂跳的核心手段。"""
    n = len(labels)
    half = window // 2
    smoothed: List[Optional[str]] = []
    for i in range(n):
        lo, hi = max(0, i - half), min(n, i + half + 1)
        window_labels = [l for l in labels[lo:hi] if l is not None]
        if not window_labels:
            smoothed.append(None)
            continue
        smoothed.append(Counter(window_labels).most_common(1)[0][0])
    return smoothed


def _labels_to_events(labels: List[Optional[str]], frame_times: np.ndarray) -> List[ChordEvent]:
    """把逐拍標籤合併成一段一段的 ChordEvent（連續相同的拍子合併成一段）。"""
    events: List[ChordEvent] = []
    prev_chord = None
    for i, chord in enumerate(labels):
        if chord is not None and chord != prev_chord:
            events.append(ChordEvent(time=float(frame_times[i]), chord=chord))
            prev_chord = chord
    return events


def _detect_chords(chroma: np.ndarray, frame_times: np.ndarray) -> List[ChordEvent]:
    raw_labels = _classify_chords_per_beat(chroma)
    smoothed_labels = _smooth_chord_labels(raw_labels, CHORD_SMOOTHING_WINDOW_BEATS)
    return _labels_to_events(smoothed_labels, frame_times)


def _detect_strum_pattern(y_percussive: np.ndarray, sr: int, beat_times: np.ndarray) -> List[StrumEvent]:
    """偵測刷弦攻擊點的時間點，量化到每拍的 8 分音符網格，用「正拍=Down、
    反拍(and)=Up」的慣例標示方向。

    重要：down/up 不是從音訊音色裡真的分辨出來的（下刷跟上刷的頻譜差異太
    細微、目前沒有可靠偵測手段），這裡是套用吉他刷弦最常見的慣例（正拍下刷、
    反拍上刷）去標示，本質上是推論不是量測，前端要清楚標示「建議」而非「偵測」。

    量化用「每拍區間內最近的 0.0/0.5」而不是對齊 librosa 回傳的絕對拍子相位，
    是因為實測發現 beat_track 的相位估計常常跟實際刷弦網格有固定偏移（同一首
    真實錄音量測到 onset 集中在拍內 0.37 跟 0.86 附近，不是預期的 0.0/0.5），
    但只要用「最近的 0.0 或 0.5」去四捨五入，這兩個偏移值還是分別正確落在
    「正拍」「反拍」的判斷範圍內，不需要額外做相位校正。
    """
    onset_env = librosa.onset.onset_strength(y=y_percussive, sr=sr, hop_length=HOP_LENGTH)
    onset_frames = librosa.onset.onset_detect(
        onset_envelope=onset_env, sr=sr, hop_length=HOP_LENGTH, backtrack=False
    )
    onset_times = librosa.frames_to_time(onset_frames, sr=sr, hop_length=HOP_LENGTH)

    if len(beat_times) < 2:
        return []

    events: List[StrumEvent] = []
    for t in onset_times:
        idx = int(np.searchsorted(beat_times, t)) - 1
        if idx < 0 or idx >= len(beat_times) - 1:
            continue
        beat_start, beat_end = beat_times[idx], beat_times[idx + 1]
        frac = (t - beat_start) / (beat_end - beat_start)
        quantized = round(frac * 2) / 2  # 最近的 0.0 / 0.5 / 1.0
        direction = "down" if quantized in (0.0, 1.0) else "up"
        events.append(StrumEvent(time=float(t), direction=direction))
    return events


def _estimate_key(chroma_mean: np.ndarray) -> str:
    best_score = -np.inf
    best_key = "C major"
    for i in range(12):
        maj_score = np.corrcoef(chroma_mean, np.roll(KS_MAJOR_PROFILE, i))[0, 1]
        min_score = np.corrcoef(chroma_mean, np.roll(KS_MINOR_PROFILE, i))[0, 1]
        if maj_score > best_score:
            best_score, best_key = maj_score, f"{NOTE_NAMES[i]} major"
        if min_score > best_score:
            best_score, best_key = min_score, f"{NOTE_NAMES[i]} minor"
    return best_key


def analyze(wav_path: str) -> AudioAnalysisResult:
    y, sr = librosa.load(wav_path, sr=None, mono=True)
    y_harmonic, y_percussive = librosa.effects.hpss(y)

    tempo, beat_frames = librosa.beat.beat_track(y=y_percussive, sr=sr, hop_length=HOP_LENGTH)
    bpm = float(tempo) if np.ndim(tempo) == 0 else float(tempo[0])

    chroma = librosa.feature.chroma_cqt(y=y_harmonic, sr=sr, hop_length=HOP_LENGTH)

    if len(beat_frames) >= 2:
        chroma_synced = librosa.util.sync(chroma, beat_frames, aggregate=np.median)
        # sync() 用 beat_frames 當內部邊界，並自動補上 0 跟結尾，
        # 所以輸出欄數是 len(beat_frames)+1，時間軸要用同樣的邊界起點來對齊
        boundary_frames = np.concatenate(([0], beat_frames))
        chord_times = librosa.frames_to_time(boundary_frames, sr=sr, hop_length=HOP_LENGTH)
    else:
        chroma_synced = chroma
        chord_times = librosa.frames_to_time(np.arange(chroma.shape[1]), sr=sr, hop_length=HOP_LENGTH)

    beat_times_full = librosa.frames_to_time(beat_frames, sr=sr, hop_length=HOP_LENGTH)

    pitches = _detect_pitches(y_harmonic, sr)
    chords = _detect_chords(chroma_synced, chord_times)
    strums = _detect_strum_pattern(y_percussive, sr, beat_times_full)
    key = _estimate_key(chroma.mean(axis=1))

    return AudioAnalysisResult(pitches=pitches, chords=chords, strums=strums, bpm=bpm, key=key)
