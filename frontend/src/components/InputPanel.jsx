import { useRef, useState } from "react";

const ACCEPTED_EXTENSIONS = [".mp3", ".mp4", ".m4a", ".wav"];

export default function InputPanel({ onStart, disabled }) {
  const [tab, setTab] = useState("url");
  const [url, setUrl] = useState("");
  const [file, setFile] = useState(null);
  const [dragOver, setDragOver] = useState(false);
  const fileInputRef = useRef(null);

  const canStart = disabled ? false : tab === "url" ? url.trim().length > 0 : !!file;

  const handleStart = () => {
    if (!canStart) return;
    if (tab === "url") {
      onStart({ type: "url", value: url.trim() });
    } else {
      onStart({ type: "file", value: file });
    }
  };

  const handleDrop = (e) => {
    e.preventDefault();
    setDragOver(false);
    const dropped = e.dataTransfer.files?.[0];
    if (dropped) setFile(dropped);
  };

  return (
    <div className="space-y-4">
      <div className="flex gap-2">
        <button
          type="button"
          onClick={() => setTab("url")}
          className={`flex-1 rounded-lg border px-4 py-2 font-medium transition-colors ${
            tab === "url" ? "border-accent bg-accent/10 text-accent" : "border-detail/20 text-detail/70"
          }`}
        >
          🔗 YouTube URL
        </button>
        <button
          type="button"
          onClick={() => setTab("file")}
          className={`flex-1 rounded-lg border px-4 py-2 font-medium transition-colors ${
            tab === "file" ? "border-accent bg-accent/10 text-accent" : "border-detail/20 text-detail/70"
          }`}
        >
          📁 上傳檔案
        </button>
      </div>

      {tab === "url" ? (
        <input
          type="url"
          value={url}
          onChange={(e) => setUrl(e.target.value)}
          placeholder="https://www.youtube.com/watch?v=..."
          disabled={disabled}
          className="w-full rounded-lg border border-detail/20 bg-transparent px-4 py-3 font-ui text-detail placeholder:text-detail/40 focus:border-accent focus:outline-none disabled:opacity-50"
        />
      ) : (
        <div
          onDragOver={(e) => {
            e.preventDefault();
            setDragOver(true);
          }}
          onDragLeave={() => setDragOver(false)}
          onDrop={handleDrop}
          onClick={() => fileInputRef.current?.click()}
          className={`cursor-pointer rounded-lg border-2 border-dashed px-4 py-8 text-center transition-colors ${
            dragOver ? "border-accent bg-accent/10" : "border-detail/20"
          } ${disabled ? "opacity-50 pointer-events-none" : ""}`}
        >
          <input
            ref={fileInputRef}
            type="file"
            accept={ACCEPTED_EXTENSIONS.join(",")}
            className="hidden"
            onChange={(e) => setFile(e.target.files?.[0] ?? null)}
          />
          {file ? (
            <p className="text-detail">已選擇：{file.name}</p>
          ) : (
            <p className="text-detail/60">
              拖放或點擊選擇檔案（{ACCEPTED_EXTENSIONS.join(" ")}）
            </p>
          )}
        </div>
      )}

      <button
        type="button"
        disabled={!canStart}
        onClick={handleStart}
        className="w-full rounded-lg bg-accent px-4 py-3 font-semibold text-bg transition-opacity disabled:opacity-40 hover:opacity-90"
      >
        ▶ 開始分析
      </button>
    </div>
  );
}
