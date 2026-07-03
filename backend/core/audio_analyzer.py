"""AI 音訊分析 pipeline：hpss 分離 → 音高偵測 → 和弦偵測（beat-synced）→ BPM/Key 估算。

輸出的是「原始」音高清單（RawPitch，只有 note/time/midi，還沒有指板 string/fret），
弦/格指派留給 tab_generator.py（依 Step 0b 定案的最小移動距離演算法）處理，
維持單一職責：這一個模組只碰音訊訊號，不碰指板邏輯。
"""

from dataclasses import dataclass
from typing import List

import librosa
import numpy as np

from models.schemas import ChordEvent
from utils.chord_templates import get_chroma_vectors

HOP_LENGTH = 512
FMIN = librosa.note_to_hz("E2")
FMAX = librosa.note_to_hz("E6")

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


def _detect_chords(chroma: np.ndarray, frame_times: np.ndarray) -> List[ChordEvent]:
    """把每個 (beat-synced) chroma 向量跟 45 個和弦模板比對 cosine similarity。"""
    templates = get_chroma_vectors()
    names = list(templates.keys())
    matrix = np.array([templates[n] for n in names], dtype=float)
    norms = np.clip(np.linalg.norm(matrix, axis=1, keepdims=True), 1e-9, None)
    matrix_normed = matrix / norms

    events: List[ChordEvent] = []
    prev_chord = None
    for i in range(chroma.shape[1]):
        vec = chroma[:, i]
        norm = np.linalg.norm(vec)
        if norm < 1e-6:
            continue
        scores = matrix_normed @ (vec / norm)
        chord = names[int(np.argmax(scores))]
        if chord != prev_chord:
            events.append(ChordEvent(time=float(frame_times[i]), chord=chord))
            prev_chord = chord
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

    pitches = _detect_pitches(y_harmonic, sr)
    chords = _detect_chords(chroma_synced, chord_times)
    key = _estimate_key(chroma.mean(axis=1))

    return AudioAnalysisResult(pitches=pitches, chords=chords, bpm=bpm, key=key)
