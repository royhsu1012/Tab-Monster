# 🎸👾 TabMonster

**Feed it a song. Get a tab.**

輸入 YouTube URL、上傳 MP3/MP4/M4A/WAV，自動生成吉他六線譜、和弦指法圖與和弦進行時間軸。譜可能來自網路曲庫，也可能是 AI 直接分析音訊生成的，介面上會清楚標示來源。

## 功能

- **多種輸入來源**：YouTube URL、MP3/MP4/M4A/WAV 檔案上傳（MP4 自動抽取音軌）
- **三種分析模式**
  - 🌐 **搜譜優先**：先找網路譜，找不到或分數太低才 AI 分析（~15s）
  - ⚡ **並行模式**（預設）：網路搜尋跟 AI 分析同時跑，取最佳結果（~60s）
  - 🤖 **AI 分析**：跳過網路搜尋，直接對音訊做音高/和弦/BPM 分析（~45s）
- **智能來源路由**：依歌曲語言（zh-TW / zh-CN / en / ja / ko）跟曲風自動決定要搜哪些譜庫、用什麼順序
- **六線譜 + 和弦指法圖 + 和弦時間軸**，找到多個來源時可以切換比較

## 技術棧

| 分類 | 技術 |
|---|---|
| Backend | Python 3.11、FastAPI、SSE 串流 |
| 音訊處理 | yt-dlp、ffmpeg、librosa、mido、PyGuitarPro、music21、mutagen |
| 找譜 | httpx（async）、BeautifulSoup4、lxml |
| Frontend | React 18、Vite、Tailwind CSS |
| 部署 | Docker Compose |

## 快速開始

### Docker Compose（推薦）

```bash
cp .env.example .env
docker compose up --build
```

- 前端：http://localhost:4173
- 後端 API：http://localhost:8000/api/health

### 本機開發

需要先裝好 Python 3.11+、Node.js 18+、[ffmpeg](https://ffmpeg.org/)。

```bash
# Backend
cd backend
python -m venv .venv
.venv/Scripts/activate   # Windows；Mac/Linux 用 source .venv/bin/activate
pip install -r requirements.txt
uvicorn main:app --reload

# Frontend（另開一個終端機）
cd frontend
npm install
npm run dev
```

Vite dev server 會把 `/api` 開發時期的請求 proxy 到 `http://localhost:8000`。

## API

| Endpoint | 說明 |
|---|---|
| `GET /api/health` | 健康檢查 |
| `GET /api/analyze/stream?url={youtube_url}&mode={web_first\|ai_only\|parallel}` | YouTube 分析，SSE 串流 |
| `POST /api/analyze/file/stream?mode={...}`（multipart，欄位 `file`） | 檔案上傳分析，SSE 串流 |

SSE 事件格式：`{"step": string, "message": string, "data": object | null}`，`step="done"` 時 `data.result` 是完整結果，`step="error"` 時 `data.code` 是錯誤碼。

## 專案結構

```
backend/
  main.py              FastAPI + SSE endpoints
  core/                音訊擷取、歌曲辨識、AI 分析、六線譜生成、GP 解析、
                        找譜路由、結果合併、總調度 pipeline
  core/sources/         7 個找譜來源模組（91pu、91jtp、GProTab、
                        GuitarProTabs、Songsterr、Ultimate Guitar、Chordie）
  models/schemas.py     所有 API 資料模型
  utils/                45 種和弦模板、MIDI 輔助函式

frontend/
  src/App.jsx           主畫面
  src/components/       ModeSelector、InputPanel、ProgressLog、SourceBadge、
                        TabDisplay、ChordDiagram、ChordGrid、ChordTimeline
  src/hooks/useAnalyze.js   SSE 消費邏輯
```

## 已知限制

- **找譜來源不保證都有結果**：GProTab.net、GuitarProTabs.org 的搜尋頁面看起來需要瀏覽器執行 JS 才會補上結果，目前的 httpx 版本抓不到；Ultimate Guitar 有 Cloudflare 反爬蟲會直接擋掉；91jtp.com 有滑動驗證（CAPTCHA）。這些來源目前會安全地回傳空結果，自動退回其他來源或 AI 分析，不會讓整個流程掛掉。
- **語言判斷**：中文語言判斷（zh-TW / zh-CN）只靠字元寫法（簡體/繁體字集合），沒有維護藝人名單，邊界案例可能誤判。純漢字、tags 也沒有假名線索的日文標題同樣可能被誤判為中文。
- **AI 生成的譜準確度約 70-80%**，僅供參考，不是精確轉譜。

## 版權聲明

所有網路譜內容僅供個人學習使用，不得商業化或再發布。
