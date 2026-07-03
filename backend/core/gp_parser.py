"""Step 8：解析 Guitar Pro（.gp/.gp3/.gp4/.gp5）檔案，取吉他軌轉成 TabResult。

重要細節（用 PyGuitarPro 實際 API 內省確認，不是憑印象猜的）：
GP 檔內的 string 編號慣例是 1=最高音弦(e)、6=最低音弦(E)，跟本專案
schemas.NotePosition 的 1=低E、6=高e 定義正好相反，換算式為 our_string = 7 - note.string。
"""

import re
from typing import List, Optional, Tuple

import guitarpro

from core.tab_generator import notes_to_ascii
from models.schemas import NotePosition, TabResult

GUITAR_MIDI_PROGRAMS = set(range(24, 32))
NOTE_NAMES = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]
_KEY_NAME_RE = re.compile(r"^([A-G])(Sharp|Flat)?(Major|Minor)$")


def _midi_to_note_name(midi_value: int) -> str:
    octave, semitone = divmod(midi_value, 12)
    return f"{NOTE_NAMES[semitone]}{octave - 1}"


def _format_key(key_signature) -> Optional[str]:
    """GP 的 KeySignature.name 長得像 'CMajor'/'CMajorFlat'，轉成跟
    audio_analyzer._estimate_key() 一致的 'C major'/'Cb major' 格式。"""
    if key_signature is None:
        return None
    match = _KEY_NAME_RE.match(key_signature.name)
    if not match:
        return key_signature.name
    root, accidental, quality = match.groups()
    acc_symbol = {"Sharp": "#", "Flat": "b"}.get(accidental, "")
    return f"{root}{acc_symbol} {quality.lower()}"


def _select_guitar_track(song) -> Tuple[object, List[str]]:
    guitar_tracks = [
        t for t in song.tracks
        if not t.isPercussionTrack and t.channel.instrument in GUITAR_MIDI_PROGRAMS
    ]
    if guitar_tracks:
        return guitar_tracks[0], []
    if song.tracks:
        first = song.tracks[0]
        return first, [f"找不到明確標示吉他音色的音軌，改用第一軌「{first.name}」，可能不是吉他"]
    raise ValueError("GP 檔案沒有任何音軌")


def _extract_notes(track) -> List[NotePosition]:
    notes: List[NotePosition] = []
    idx = 0
    for measure in track.measures:
        for voice in measure.voices:
            for beat in voice.beats:
                for note in beat.notes:
                    our_string = 7 - note.string
                    if not (1 <= our_string <= 6):
                        continue
                    notes.append(NotePosition(
                        note=_midi_to_note_name(note.realValue),
                        string=our_string,
                        fret=note.value,
                        idx=idx,
                    ))
                    idx += 1
    return notes


def _extract_chords(track) -> List[str]:
    chords: List[str] = []
    for measure in track.measures:
        for voice in measure.voices:
            for beat in voice.beats:
                chord = beat.effect.chord if beat.effect else None
                name = getattr(chord, "name", None) if chord else None
                if name and (not chords or chords[-1] != name):
                    chords.append(name)
    return chords


def parse_gp_file(
    filepath: str,
    source: str,
    source_url: Optional[str] = None,
) -> Tuple[TabResult, dict, List[str]]:
    """回傳 (TabResult, {bpm, key, chords}, warnings)。"""
    song = guitarpro.parse(filepath)
    track, warnings = _select_guitar_track(song)
    notes = _extract_notes(track)
    chords = _extract_chords(track)

    tab_result = TabResult(
        ascii=notes_to_ascii(notes),
        notes=notes,
        tab_type="guitar_pro",
        source=source,
        source_url=source_url,
        rating=None,
        score=100.0,
    )
    meta = {
        "bpm": float(song.tempo),
        "key": _format_key(song.key),
        "chords": chords,
    }
    return tab_result, meta, warnings
