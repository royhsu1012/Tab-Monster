"""Step 7：音符 → MIDI / ASCII 六線譜。

弦/格指派套用 Step 0b 定案的「最小移動距離」貪婪演算法：
每個音符找出指板上所有可能的 (string, fret) 候選，優先選擇跟前一個音符
把位最接近的位置，減少不必要的大跳把位；第一個音符沒有前例可循時，
偏好第 2~5 品這種初學者友善的起手位置。
"""

import io
from typing import List, Optional, Tuple

import mido

from core.audio_analyzer import RawPitch
from models.schemas import NotePosition, TabResult

# string: 1=低音 E, 6=高音 e（對齊 schemas.NotePosition 的定義）
STRING_OPEN_MIDI = {1: 40, 2: 45, 3: 50, 4: 55, 5: 59, 6: 64}
MAX_FRET = 20
PREFERRED_OPENING_FRET_RANGE = (2, 5)
STRING_LABELS = {6: "e", 5: "B", 4: "G", 3: "D", 2: "A", 1: "E"}
COL_WIDTH = 3


def _candidates(midi: int) -> List[Tuple[int, int]]:
    return [
        (string, midi - open_midi)
        for string, open_midi in STRING_OPEN_MIDI.items()
        if 0 <= midi - open_midi <= MAX_FRET
    ]


def _pick_position(midi: int, prev_fret: Optional[float]) -> Optional[Tuple[int, int]]:
    candidates = _candidates(midi)
    if not candidates:
        return None
    if prev_fret is None:
        lo, hi = PREFERRED_OPENING_FRET_RANGE
        pool = [c for c in candidates if lo <= c[1] <= hi] or candidates
        return min(pool, key=lambda c: (c[1], -c[0]))
    return min(candidates, key=lambda c: (abs(c[1] - prev_fret), c[1]))


def pitches_to_notes(pitches: List[RawPitch]) -> List[NotePosition]:
    notes: List[NotePosition] = []
    prev_fret: Optional[float] = None
    idx = 0
    for p in pitches:
        pos = _pick_position(p.midi, prev_fret)
        if pos is None:
            continue
        string, fret = pos
        notes.append(NotePosition(note=p.note, string=string, fret=fret, idx=idx))
        prev_fret = float(fret)
        idx += 1
    return notes


def notes_to_ascii(notes: List[NotePosition]) -> str:
    if not notes:
        return "(no notes detected)"
    max_idx = max(n.idx for n in notes)
    width = (max_idx + 1) * COL_WIDTH + 1
    lines = {s: ["-"] * width for s in range(1, 7)}
    for n in notes:
        col = n.idx * COL_WIDTH + 1
        for i, ch in enumerate(str(n.fret)):
            if col + i < width:
                lines[n.string][col + i] = ch
    return "\n".join(f"{STRING_LABELS[s]}|" + "".join(lines[s]) + "|" for s in (6, 5, 4, 3, 2, 1))


def generate_midi_bytes(notes: List[NotePosition], bpm: float) -> bytes:
    mid = mido.MidiFile()
    track = mido.MidiTrack()
    mid.tracks.append(track)
    track.append(mido.MetaMessage("set_tempo", tempo=mido.bpm2tempo(max(bpm, 1.0)), time=0))
    track.append(mido.Message("program_change", program=24, time=0))  # nylon guitar

    ticks_per_note = mid.ticks_per_beat // 2
    for n in notes:
        midi_note = STRING_OPEN_MIDI[n.string] + n.fret
        track.append(mido.Message("note_on", note=midi_note, velocity=80, time=0))
        track.append(mido.Message("note_off", note=midi_note, velocity=64, time=ticks_per_note))

    buf = io.BytesIO()
    mid.save(file=buf)
    return buf.getvalue()


def generate_tab(pitches: List[RawPitch], bpm: float, source: str = "ai_analysis") -> TabResult:
    notes = pitches_to_notes(pitches)
    return TabResult(
        ascii=notes_to_ascii(notes),
        notes=notes,
        tab_type="ai",
        source=source,
        source_url=None,
        rating=None,
        score=40.0 if notes else 0.0,
    )
