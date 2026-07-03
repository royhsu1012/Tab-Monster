"""45+ 吉他和弦模板：chroma vector（供 AI 和弦偵測比對）+ 指法（供 ChordDiagram 顯示）。

fingering 順序為 [E, A, D, G, B, e]（低音到高音），-1 = 悶音，0 = 空弦。
chroma 為 12 維 one-hot-ish 向量，index 0=C, 1=C#, ... 11=B。
"""

from typing import Dict, List, Optional, TypedDict

NOTE_INDEX = {
    "C": 0, "C#": 1, "Db": 1, "D": 2, "D#": 3, "Eb": 3, "E": 4, "F": 5,
    "F#": 6, "Gb": 6, "G": 7, "G#": 8, "Ab": 8, "A": 9, "A#": 10, "Bb": 10,
    "B": 11,
}

INTERVALS = {
    "major": (0, 4, 7),
    "minor": (0, 3, 7),
    "dom7": (0, 4, 7, 10),
    "sus2": (0, 2, 7),
    "sus4": (0, 5, 7),
    "add9": (0, 2, 4, 7),
}


class ChordEntry(TypedDict):
    chroma: List[int]
    fingering: List[int]
    barre_fret: Optional[int]


def _chroma(root: str, quality: str) -> List[int]:
    root_idx = NOTE_INDEX[root]
    vec = [0] * 12
    for interval in INTERVALS[quality]:
        vec[(root_idx + interval) % 12] = 1
    return vec


def _entry(root: str, quality: str, fingering: List[int], barre_fret: Optional[int] = None) -> ChordEntry:
    return {"chroma": _chroma(root, quality), "fingering": fingering, "barre_fret": barre_fret}


CHORD_DATA: Dict[str, ChordEntry] = {
    # ── 大調 12 種 ──
    "C":  _entry("C", "major", [-1, 3, 2, 0, 1, 0]),
    "C#": _entry("C#", "major", [-1, 4, 6, 6, 6, 4], barre_fret=4),
    "D":  _entry("D", "major", [-1, -1, 0, 2, 3, 2]),
    "D#": _entry("D#", "major", [-1, 6, 8, 8, 8, 6], barre_fret=6),
    "E":  _entry("E", "major", [0, 2, 2, 1, 0, 0]),
    "F":  _entry("F", "major", [1, 3, 3, 2, 1, 1], barre_fret=1),
    "F#": _entry("F#", "major", [2, 4, 4, 3, 2, 2], barre_fret=2),
    "G":  _entry("G", "major", [3, 2, 0, 0, 0, 3]),
    "G#": _entry("G#", "major", [4, 6, 6, 5, 4, 4], barre_fret=4),
    "A":  _entry("A", "major", [-1, 0, 2, 2, 2, 0]),
    "A#": _entry("A#", "major", [-1, 1, 3, 3, 3, 1], barre_fret=1),
    "B":  _entry("B", "major", [-1, 2, 4, 4, 4, 2], barre_fret=2),

    # ── 小調 12 種 ──
    "Cm":  _entry("C", "minor", [-1, 3, 5, 5, 4, 3], barre_fret=3),
    "C#m": _entry("C#", "minor", [-1, 4, 6, 6, 5, 4], barre_fret=4),
    "Dm":  _entry("D", "minor", [-1, -1, 0, 2, 3, 1]),
    "D#m": _entry("D#", "minor", [-1, 6, 8, 8, 7, 6], barre_fret=6),
    "Em":  _entry("E", "minor", [0, 2, 2, 0, 0, 0]),
    "Fm":  _entry("F", "minor", [1, 3, 3, 1, 1, 1], barre_fret=1),
    "F#m": _entry("F#", "minor", [2, 4, 4, 2, 2, 2], barre_fret=2),
    "Gm":  _entry("G", "minor", [3, 5, 5, 3, 3, 3], barre_fret=3),
    "G#m": _entry("G#", "minor", [4, 6, 6, 4, 4, 4], barre_fret=4),
    "Am":  _entry("A", "minor", [-1, 0, 2, 2, 1, 0]),
    "A#m": _entry("A#", "minor", [-1, 1, 3, 3, 2, 1], barre_fret=1),
    "Bm":  _entry("B", "minor", [-1, 2, 4, 4, 3, 2], barre_fret=2),

    # ── 屬七和弦 9 種 ──
    "C7":  _entry("C", "dom7", [-1, 3, 2, 3, 1, 0]),
    "D7":  _entry("D", "dom7", [-1, -1, 0, 2, 1, 2]),
    "D#7": _entry("D#", "dom7", [-1, 6, 8, 6, 8, 6], barre_fret=6),
    "E7":  _entry("E", "dom7", [0, 2, 0, 1, 0, 0]),
    "F7":  _entry("F", "dom7", [1, 3, 1, 2, 1, 1], barre_fret=1),
    "G7":  _entry("G", "dom7", [3, 2, 0, 0, 0, 1]),
    "A7":  _entry("A", "dom7", [-1, 0, 2, 0, 2, 0]),
    "A#7": _entry("A#", "dom7", [-1, 1, 3, 1, 3, 1], barre_fret=1),
    "B7":  _entry("B", "dom7", [-1, 2, 1, 2, 0, 2]),

    # ── 掛留和弦 6 種（sus2/sus4）──
    "Asus2": _entry("A", "sus2", [-1, 0, 2, 2, 0, 0]),
    "Asus4": _entry("A", "sus4", [-1, 0, 2, 2, 3, 0]),
    "Dsus2": _entry("D", "sus2", [-1, -1, 0, 2, 3, 0]),
    "Dsus4": _entry("D", "sus4", [-1, -1, 0, 2, 3, 3]),
    "Esus4": _entry("E", "sus4", [0, 2, 2, 2, 0, 0]),
    "Csus2": _entry("C", "sus2", [-1, 3, 0, 0, 1, 3]),

    # ── 加九和弦 6 種（add9）──
    "Cadd9": _entry("C", "add9", [-1, 3, 2, 0, 3, 3]),
    "Dadd9": _entry("D", "add9", [-1, 5, 4, 2, 3, 0]),
    "Gadd9": _entry("G", "add9", [3, 2, 0, 2, 0, 3]),
    "Aadd9": _entry("A", "add9", [-1, 0, 2, 4, 2, 0]),
    "Eadd9": _entry("E", "add9", [0, 2, 2, 1, 0, 2]),
    "Fadd9": _entry("F", "add9", [1, 3, 3, 0, 1, 1], barre_fret=1),
}


def get_chroma_vectors() -> Dict[str, List[int]]:
    """供 audio_analyzer.py 做 chroma 比對用的 {chord_name: chroma} 對照表。"""
    return {name: data["chroma"] for name, data in CHORD_DATA.items()}
