<div align="center">

<br>

# 🎸👾 TabMonster

### Feed it a song. Get a tab.

輸入 YouTube URL 或上傳音訊檔案，自動生成吉他六線譜、和弦指法圖與和弦進行時間軸
**網路曲庫 + AI 音訊分析雙軌並行**，找不到譜也能靠音高/和弦偵測生成一份可用的譜

<br>

[![Python](https://img.shields.io/badge/Python-3.11+-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-SSE-009688?style=for-the-badge&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![React](https://img.shields.io/badge/React-18-61DAFB?style=for-the-badge&logo=react&logoColor=black)](https://react.dev)
[![Vite](https://img.shields.io/badge/Vite-5-646CFF?style=for-the-badge&logo=vite&logoColor=white)](https://vitejs.dev)
[![Docker](https://img.shields.io/badge/Docker-Compose-2496ED?style=for-the-badge&logo=docker&logoColor=white)](https://docker.com)

<br>

![Modes](https://img.shields.io/badge/分析模式-3_種-6366f1?style=flat-square)
![Chords](https://img.shields.io/badge/和弦模板-45_種-f59e0b?style=flat-square)
![Sources](https://img.shields.io/badge/找譜來源-7_個-8b5cf6?style=flat-square)
![Streaming](https://img.shields.io/badge/進度回報-SSE_即時串流-22c55e?style=flat-square)

<br>

> 輸入任何一首歌，系統先辨識語言/曲風，依此路由到對應的網路譜庫搜尋；
> 同時（或視模式而定）用 librosa 對音訊做和聲分離、音高偵測、和弦比對，
> 兩邊的結果最後合併成一份標示清楚來源的六線譜。任一來源失效都不會讓整個流程掛掉。

</div>

---

## 目錄

- [系統概覽](#系統概覽)
- [技術棧](#技術棧)
- [架構總覽](#架構總覽)
- [核心工程決策](#核心工程決策)
- [三種分析模式](#三種分析模式)
- [找譜來源路由](#找譜來源路由)
- [45 種和弦模板](#45-種和弦模板)
- [SSE 事件契約](#sse-事件契約)
- [專案結構](#專案結構)
- [部署](#部署)
- [已知限制](#已知限制)

---

## 系統概覽

```
YouTube URL / MP3 / MP4 / WAV
              ↓
        音訊擷取（yt-dlp / ffmpeg）→ 標準化 WAV
              ↓
        歌曲辨識（語言 / 曲風 / artist / title）
              ↓
    ┌─────────────────────┬─────────────────────┐
    │   🌐 網路搜譜         │   🤖 AI 音訊分析       │
    │   依語言/曲風路由      │   hpss → 音高 → 和弦   │
    │   到 7 個曲庫來源      │   → BPM/Key           │
    └─────────────────────┴─────────────────────┘
              ↓
        結果合併（評分排序，網路譜優先，AI 補時間軸）
              ↓
     六線譜 + 和弦指法圖 + 和弦時間軸（含來源標示）
```

| 面向 | 內容 |
|------|------|
| 輸入 | YouTube URL、MP3/MP4/M4A/WAV 上傳（MP4 自動抽音軌） |
| 分析模式 | 搜譜優先 / AI 分析 / 並行（三選一，見下方詳表） |
| 找譜來源 | 91譜、91jtp、GProTab、GuitarProTabs、Songsterr、Ultimate Guitar、Chordie |
| 語言路由 | zh-TW / zh-CN / en / ja / ko / other，依語言+曲風決定搜哪些來源、順序 |
| 進度回報 | 全程 SSE 串流，前端即時顯示「搜尋第幾個來源」「AI 分析到哪一步」 |
| 容錯設計 | 任一來源逾時/改版/被擋一律靜默跳過，不中斷整體流程 |

---

## 技術棧

| 層次 | 技術 |
|------|------|
| **後端** | Python 3.11 · FastAPI · Server-Sent Events |
| **音訊處理** | yt-dlp · ffmpeg · librosa · mido · PyGuitarPro · music21 · mutagen |
| **找譜** | httpx（async）· BeautifulSoup4 · lxml |
| **前端** | React 18 · Vite · Tailwind CSS |
| **部署** | Docker Compose（backend + frontend 兩個 service） |

---

## 架構總覽

```
┌───────────────────────────────────────────────────────────────┐
│                    Frontend（React + Vite）                    │
│  App.jsx → InputPanel / ModeSelector / ProgressLog / TabDisplay │
│  useAnalyze.js：fetch + ReadableStream 手動解析 SSE              │
│  （不用原生 EventSource，因為上傳檔案是 POST + multipart）        │
└──────────────────────────────┬────────────────────────────────┘
                                │ SSE (text/event-stream)
                                ▼
┌───────────────────────────────────────────────────────────────┐
│                  Backend（FastAPI, main.py）                   │
│  /api/analyze/stream         /api/analyze/file/stream           │
│         └──────────────┬──────────────┘                        │
│                         ▼                                       │
│                  core/pipeline.py（三模式總調度）                │
│   ┌─────────────┐  ┌──────────────┐  ┌─────────────────────┐   │
│   │ audio_       │  │ song_        │  │ tab_searcher +       │   │
│   │ extractor    │  │ identifier   │  │ sources/*（7 個）     │   │
│   │ audio_       │  │              │  │ result_merger        │   │
│   │ analyzer     │  │              │  │ gp_parser             │   │
│   │ tab_generator│  │              │  │                       │   │
│   └─────────────┘  └──────────────┘  └─────────────────────┘   │
└───────────────────────────────────────────────────────────────┘
```

---

## 核心工程決策

### 1. librosa 丟執行緒池，parallel 模式才是真的並行
`audio_analyzer.analyze()` 是同步、CPU 密集的呼叫。如果直接 `await` 會卡住 event loop，parallel 模式下網路搜尋跟 AI 分析就變成假並行（實際上還是排隊）。改用 `asyncio.to_thread()` 丟到執行緒池，兩邊才真的能同時跑。

```python
# core/pipeline.py
analysis = await asyncio.to_thread(audio_analyzer.analyze, str(wav_path))
```

### 2. 找譜來源全面「靜默失敗」，不拖垮整體流程
7 個來源裡有 4 個實測是 JS 渲染或有反爬蟲機制（見〈已知限制〉）。`search_sources()` 用 `asyncio.gather` 平行呼叫全部來源，個別來源丟例外只記警告、當作沒找到，其餘來源跟 AI 分析完全不受影響。

```python
# core/tab_searcher.py
async def _run_one(name):
    try:
        return await SOURCE_REGISTRY[name](artist, title)
    except Exception:
        logger.warning("source %s failed, skipping silently", name, exc_info=True)
        return None
```

### 3. Guitar Pro 檔案的弦編號是反的，用 API 內省避免憑印象猜錯
GP 檔案格式裡 `string=1` 是最高音的 e 弦、`string=6` 是最低音的 E 弦，跟本專案 schema 定義的 `1=低音E、6=高音e` 正好相反。這個細節沒有反查 PyGuitarPro 原始碼跟寫一個真實 `.gp5` 檔案測試回讀，很容易在音符對應上錯位卻沒有任何錯誤訊息。換算式：`our_string = 7 - note.string`。

### 4. pitch → 指板位置：最小移動距離貪婪演算法
規格原本要用的 `tayuya` 套件最後一次更新是 2019 年、已停止維護 6 年，改成自己寫。同一個音高在指板上通常有多個可能位置，演算法優先選離前一個音符把位最近的候選，讓生成的六線譜不會無意義地在把位間亂跳。

### 5. SSRF 白名單 + 上傳驗證 + 內容一律當純文字渲染
YouTube URL 輸入限制在官方網域白名單內，避免 `yt-dlp` 被拿去當跳板打任意網站；上傳檔案限制副檔名白名單。前端 `TabDisplay` 把抓回來的第三方譜面內容放進 `<pre>{text}</pre>`，一律走 React 預設跳脫，不用 `dangerouslySetInnerHTML`，防止惡意譜面內容夾帶 script。

### 6. 和弦偵測用 beat-synced chroma，不是逐 frame 比對
如果每個音框（512 samples）都獨立比對和弦模板，同一個和弦會因為些微音色變化被切成一堆雜訊般的短暫和弦事件。改成用 `librosa.util.sync()` 把 chroma 依偵測到的節拍分組平均後再比對，一個和弦才會對應到一段合理長度的時間區間。

---

## 三種分析模式

| 模式 | 說明 | 預估時間 | 適合情境 |
|------|------|----------|----------|
| 🌐 搜譜優先 `web_first` | 先搜網路譜，分數 ≥60 才直接採用；不夠高則再跑 AI 分析比對 | ~15s | 熱門歌曲，網路上大機率有現成譜 |
| ⚡ 並行模式 `parallel`（預設） | 網路搜尋 + AI 分析同時開始，取分數較高的當主譜 | ~60s | 不確定網路上有沒有譜，想要最佳結果 |
| 🤖 AI 分析 `ai_only` | 跳過網路搜尋，直接對音訊做 hpss → 音高 → 和弦 → BPM 分析 | ~45s | 冷門歌曲、翻唱、找不到譜 |

---

## 找譜來源路由

依歌曲的語言與曲風決定要打哪些來源、用什麼順序（`core/tab_searcher.py` 的 `SOURCE_ROUTING`）：

| 語言 / 曲風 | 路由順序 |
|---|---|
| zh-TW / pop | 91pu → 91jtp → Ultimate Guitar → Chordie |
| zh-CN / pop | 91jtp → 91pu → Ultimate Guitar → Chordie |
| en / pop | GProTab → GuitarProTabs → Songsterr → Ultimate Guitar → Chordie |
| en / rock_metal | Songsterr → GProTab → GuitarProTabs → Ultimate Guitar |
| ja / pop | GProTab → Ultimate Guitar |
| \* / anime_game | GProTab → GuitarProTabs → Ultimate Guitar |
| ko / \*、other / \* | 不搜網路，直接 AI 分析 |

評分公式：`base(guitar_pro=100 / full_tab=60 / chords=20) + rating×5 + min(votes/100, 20)`，分數最高的結果當主譜。

---

## 45 種和弦模板

`utils/chord_templates.py` 涵蓋大調 12、小調 12、屬七和弦 9、掛留和弦 6、加九和弦 6 種，每個和弦的 chroma 向量用根音+音程公式**程式計算**而非手key（避免手動輸入 12 維向量出錯），指法則逐一用指板音名對照驗證過：

```python
INTERVALS = {
    "major": (0, 4, 7), "minor": (0, 3, 7), "dom7": (0, 4, 7, 10),
    "sus2": (0, 2, 7), "sus4": (0, 5, 7), "add9": (0, 2, 4, 7),
}
```

---

## SSE 事件契約

| Endpoint | 說明 |
|---|---|
| `GET /api/analyze/stream?url={youtube_url}&mode={mode}` | YouTube 分析 |
| `POST /api/analyze/file/stream?mode={mode}`（multipart, field=`file`） | 檔案上傳分析 |
| `GET /api/health` | 健康檢查 |

事件格式：`{"step": string, "message": string, "data": object | null}`

| `step` 範例 | 時機 |
|---|---|
| `extract` | 音訊擷取/轉檔中 |
| `identify` | 歌曲辨識完成（附 `data.song`） |
| `route` | 依語言/曲風選定搜尋來源（附 `data.sources`） |
| `search:{source}` | 單一來源搜尋完成 |
| `ai:hpss` / `ai:pitch` / `ai:chords` / `ai:bpm` | AI 分析各階段 |
| `generate:midi` / `generate:tab` | 產生 MIDI / 六線譜 |
| `done` | 完成，`data.result` 是完整 `TabMonsterResult` |
| `error` | 失敗，`data.code` 對應六種錯誤碼之一 |

錯誤碼：`YOUTUBE_UNAVAILABLE` · `UNSUPPORTED_FORMAT` · `AUDIO_TOO_SHORT` · `SONG_UNIDENTIFIABLE` · `ANALYSIS_FAILED` · `ALL_SOURCES_FAILED`

---

## 專案結構

```
backend/
  main.py                   FastAPI + SSE endpoints
  core/
    pipeline.py              三種模式總調度
    audio_extractor.py       YouTube/上傳檔案 → WAV（含 SSRF/上傳驗證）
    song_identifier.py       語言/曲風辨識
    audio_analyzer.py        librosa pipeline（hpss/pitch/chord/bpm）
    tab_generator.py         音符 → 指板位置 → ASCII 六線譜 + MIDI
    gp_parser.py             Guitar Pro 檔案解析
    tab_searcher.py          來源路由 + 平行搜尋 + 評分
    result_merger.py         合併網路譜與 AI 結果
    sources/                 7 個找譜來源模組
  models/schemas.py          所有 API 資料模型（pydantic）
  utils/chord_templates.py   45 種和弦模板

frontend/
  src/App.jsx                主畫面
  src/components/            ModeSelector, InputPanel, ProgressLog,
                              SourceBadge, TabDisplay, ChordDiagram,
                              ChordGrid, ChordTimeline
  src/hooks/useAnalyze.js    SSE 消費邏輯（fetch + ReadableStream）
```

---

## 部署

### Docker Compose

```bash
cp .env.example .env
docker compose up --build
```

前端 http://localhost:4173 ・ 後端 http://localhost:8000/api/health

### 本地開發

```bash
# Backend（需要 Python 3.11+、ffmpeg）
cd backend
python -m venv .venv && .venv/Scripts/activate
pip install -r requirements.txt
uvicorn main:app --reload

# Frontend（另開終端機，需要 Node.js 18+）
cd frontend
npm install
npm run dev
```

---

## 已知限制

| 項目 | 狀況 |
|---|---|
| GProTab.net / GuitarProTabs.org | 搜尋頁疑似需要瀏覽器執行 JS 才會補上結果，目前抓不到，會靜默跳過 |
| Ultimate Guitar | 有 Cloudflare 反爬蟲機制，直接請求會被 403 擋下 |
| 91jtp.com | 有滑動驗證（CAPTCHA），未嘗試繞過 |
| 中文語言判斷 | 只靠簡體/繁體字元集合區分 zh-CN / zh-TW，沒有藝人名單輔助 |
| 純漢字日文標題 | 若 tags 也沒有假名線索，可能被誤判為中文 |
| AI 生成譜 | 準確度約 70–80%，僅供參考，非精確轉譜 |

---

<div align="center">

<br>

**TabMonster** &ensp;·&ensp; 個人學習用途，不得商業化或再發布 &ensp;·&ensp; © 2026 Roy Hsu

*本專案由 Claude Code 協助開發*

<br>

</div>
