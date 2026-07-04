<div align="center">

<br>

# 🎸👾 TabMonster

### Feed it a song. Get a tab.

輸入 YouTube URL 或上傳音訊檔案，自動生成吉他六線譜、和弦指法圖、小節化的和弦/刷弦節奏，還會推論 Capo 位置
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
![Capo](https://img.shields.io/badge/Capo-自動偵測-ec4899?style=flat-square)
![Rhythm](https://img.shields.io/badge/刷弦節奏-小節化顯示-06b6d4?style=flat-square)
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
- [Capo 偵測 + 小節化節奏顯示](#capo-偵測--小節化節奏顯示)
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
    │   到 7 個曲庫來源      │   → 刷弦節奏 → BPM/Key │
    └─────────────────────┴─────────────────────┘
              ↓
        結果合併（評分排序，網路譜優先，AI 補時間軸）
              ↓
        Capo 位置推論（和弦/調性換算成好彈的簡單版本）
              ↓
  六線譜 + 和弦指法圖 + 小節化和弦/刷弦節奏表 + Capo 建議
```

| 面向 | 內容 |
|------|------|
| 輸入 | YouTube URL、MP3/MP4/M4A/WAV 上傳（MP4 自動抽音軌） |
| 分析模式 | 搜譜優先 / AI 分析 / 並行（三選一，見下方詳表） |
| 找譜來源 | 91譜、91jtp、GProTab、GuitarProTabs、Songsterr、Ultimate Guitar、Chordie |
| 語言路由 | zh-TW / zh-CN / en / ja / ko / other，依語言+曲風決定搜哪些來源、順序 |
| Capo 推論 | 把偵測到的和弦往下移調 0~7 品，挑「開放和弦比例」最高的位移當建議 |
| 節奏顯示 | 以小節為單位（假設 4/4 拍）分組和弦跟刷弦方向，而不是攤平的時間軸 |
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

### 7. 光靠 beat-sync 還不夠，逐拍還是會抖：加多數決平滑
用一首真實錄音實測，逐拍判斷最佳/次佳和弦候選的 cosine similarity 差距中位數只有 0.014，508 個拍子裡 58.6% 幾乎是同分猜的，230 秒的歌被切成 303 個「換和弦」事件。改成對逐拍標籤做多數決平滑（窗口用「拍」不用「秒」，才能自動適應不同 BPM），9 拍窗口把事件數降到 78 個，平均每個和弦持續約 1.7 小節，才是流行歌合理的和聲節奏。

```python
# core/audio_analyzer.py
CHORD_SMOOTHING_WINDOW_BEATS = 9  # 約 2 個小節（4/4 拍），實測調出來的
```

### 8. Capo 位置推論：用「開放和弦比例」評分，但分數接近時別死板選最高分
真人彈奏常會夾 capo 用簡單開放和弦（E/A/D/G/C）演奏，chroma 偵測到的卻是實際音高（可能是 F#、C# 這種難彈的調）。`capo_detector.py` 把和弦序列往下移調 0~7 品，用 `chord_templates.py` 已驗證過的 `barre_fret is None` 資料算開放和弦比例，選比例最高的位移。**但實測一首歌時，正確答案 capo=2 的分數（0.692）跟錯誤答案 capo=4（0.718）只差 0.026——雜訊等級，不是真訊號**。修法：分數在最高分 0.05 範圍內的候選裡，優先選最低的 capo（低把位在現實中遠比高把位常見，證據不夠壓倒性時偏好更常見的解釋）。

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

## Capo 偵測 + 小節化節奏顯示

AI 分析結果除了和弦/BPM/Key，還會做兩件事，讓輸出更接近真人會怎麼彈：

- **Capo 推論**（`core/capo_detector.py`）：和弦/調性換算成建議 capo 後的簡單版本，附在 `TabMonsterResult.suggested_capo`，前端顯示「🎸 Capo N」徽章。分數不夠有把握（跟不加 capo 比沒有明顯進步、或最高分本身太低）就不建議。
- **刷弦節奏**（`core/audio_analyzer._detect_strum_pattern`）：對打擊分量做 onset 偵測，量化到每拍最近的 8 分音符位置，用「正拍下刷 ↓・反拍上刷 ↑」的慣例標示方向。**這個方向是慣例推論，不是從音色真的分辨出來的**（下刷/上刷的頻譜差異目前沒有可靠偵測手段），程式碼跟前端文字都清楚寫明。
- **小節分組**（`result_merger.build_measures`）：假設 4/4 拍（本專案不偵測拍號），把拍子網格切成小節，每小節標上該彈的和弦跟 8 個刷弦格子，`MeasureGrid.jsx` 用真正的和弦譜排版（每格一個小節、和弦在上刷弦在下）取代早期攤平、難以閱讀的時間軸。第一小節的起點是抓拍演算法偵測到的第一個拍子，不一定跟原曲真正的小節對齊，但小節長度是準的。

實測驗證（過程見 commit history）：張震嶽《跟著感覺走》正確推論出 Capo 2（E 大調），周杰倫《晴天》C 調版本正確判斷不需要 capo，兩次小節化結果的和弦進行都跟這兩首歌實際彈法一致。

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
| `ai:hpss` / `ai:pitch` / `ai:chords` / `ai:strums` / `ai:bpm` | AI 分析各階段 |
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
    audio_analyzer.py        librosa pipeline（hpss/pitch/chord/strum/bpm）
    tab_generator.py         音符 → 指板位置 → ASCII 六線譜 + MIDI
    gp_parser.py             Guitar Pro 檔案解析
    tab_searcher.py          來源路由 + 平行搜尋 + 評分
    result_merger.py         合併網路譜與 AI 結果 + 小節分組
    capo_detector.py         Capo 位置推論 + 和弦/調性移調
    sources/                 7 個找譜來源模組
  models/schemas.py          所有 API 資料模型（pydantic）
  utils/chord_templates.py   45 種和弦模板

frontend/
  src/App.jsx                主畫面
  src/components/            ModeSelector, InputPanel, ProgressLog,
                              SourceBadge, TabDisplay, ChordDiagram,
                              ChordGrid, ChordTimeline, StrumPattern,
                              MeasureGrid
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
| 刷弦方向（↓/↑） | 是「正拍下刷、反拍上刷」的慣例推論，不是從音色真的偵測出下刷/上刷 |
| 小節/拍號 | 一律假設 4/4 拍（不偵測拍號），小節起點以抓拍演算法偵測到的第一拍為準，不保證跟原曲真正的小節對齊 |
| Capo 推論 | 只在證據夠強時才建議（跟不加 capo 相比要有明顯進步），複雜爵士和弦或本來就不是靠 capo 彈的歌可能不會有建議，這是設計上刻意保守 |
| AI 生成譜 | 準確度約 70–80%，僅供參考，非精確轉譜 |

---

<div align="center">

<br>

**TabMonster** &ensp;·&ensp; 個人學習用途，不得商業化或再發布 &ensp;·&ensp; © 2026 Roy Hsu

*本專案由 Claude Code 協助開發*

<br>

</div>
