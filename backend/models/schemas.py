from typing import Optional, List, Literal

from pydantic import BaseModel

Language = Literal["zh-TW", "zh-CN", "en", "ja", "ko", "other"]
Genre = Literal["pop", "rock_metal", "indie", "anime_game", "classical", "unknown"]
Confidence = Literal["high", "medium", "low"]
AnalysisMode = Literal["web_first", "ai_only", "parallel"]
TabType = Literal["guitar_pro", "full_tab", "chords", "ai"]


class SongInfo(BaseModel):
    artist: Optional[str] = None
    title: Optional[str] = None
    language: Language = "other"
    genre: Genre = "unknown"
    confidence: Confidence = "low"


class NotePosition(BaseModel):
    note: str
    string: int
    fret: int
    idx: int


class ChordEvent(BaseModel):
    time: float
    chord: str


class StrumEvent(BaseModel):
    time: float
    direction: Literal["down", "up"]


class ChordInfo(BaseModel):
    chord: str
    fingering: List[int]
    barre_fret: Optional[int] = None


class Measure(BaseModel):
    """一個小節（假設 4/4 拍）：小節開頭該彈的和弦 + 這個小節內每個 8 分音符
    格子的刷弦方向（None = 那一格沒有偵測到刷弦）。"""
    index: int
    start_time: float
    chord: Optional[str] = None
    strums: List[Optional[Literal["down", "up"]]] = []


class SearchResult(BaseModel):
    source: str
    source_url: str
    tab_type: Literal["guitar_pro", "full_tab", "chords"]
    tab_text: Optional[str] = None
    gp_filepath: Optional[str] = None
    chords: List[str] = []
    rating: Optional[float] = None
    votes: Optional[int] = None
    score: float = 0.0


class TabResult(BaseModel):
    ascii: str
    notes: List[NotePosition] = []
    tab_type: TabType
    source: str
    source_url: Optional[str] = None
    rating: Optional[float] = None
    score: float = 0.0


class TabMonsterResult(BaseModel):
    song: SongInfo
    bpm: float
    key: Optional[str] = None
    mode_used: str
    primary_tab: TabResult
    secondary_tab: Optional[TabResult] = None
    chords: List[ChordEvent] = []
    chord_info: List[ChordInfo] = []
    strum_pattern: List[StrumEvent] = []
    measures: List[Measure] = []
    suggested_capo: int = 0
    all_web_results: List[TabResult] = []
    sources_tried: List[str] = []
    status: str
    warnings: List[str] = []


class ProgressEvent(BaseModel):
    step: str
    message: str
    data: Optional[dict] = None
