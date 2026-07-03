"""共用錯誤碼，對應規格中六種 SSE 錯誤事件。"""

from typing import Literal

ErrorCode = Literal[
    "YOUTUBE_UNAVAILABLE",
    "UNSUPPORTED_FORMAT",
    "AUDIO_TOO_SHORT",
    "SONG_UNIDENTIFIABLE",
    "ANALYSIS_FAILED",
    "ALL_SOURCES_FAILED",
]


class TabMonsterError(Exception):
    def __init__(self, code: ErrorCode, message: str):
        self.code = code
        self.message = message
        super().__init__(f"[{code}] {message}")
