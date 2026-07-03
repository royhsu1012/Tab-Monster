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


class ChordInfo(BaseModel):
    chord: str
    fingering: List[int]
    barre_fret: Optional[int] = None


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
    all_web_results: List[TabResult] = []
    sources_tried: List[str] = []
    status: str
    warnings: List[str] = []


class ProgressEvent(BaseModel):
    step: str
    message: str
    data: Optional[dict] = None
