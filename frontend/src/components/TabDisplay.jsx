import { useState } from "react";
import ChordGrid from "./ChordGrid.jsx";
import ChordTimeline from "./ChordTimeline.jsx";
import MeasureGrid from "./MeasureGrid.jsx";
import SourceBadge from "./SourceBadge.jsx";
import StrumPattern from "./StrumPattern.jsx";

const VIEWS = [
  { key: "tab", label: "🎸 六線譜" },
  { key: "chords", label: "🖐 和弦圖" },
  { key: "timeline", label: "🕐 時間軸" },
];

export default function TabDisplay({ result }) {
  const [view, setView] = useState("tab");
  const [activeTab, setActiveTab] = useState(result.primary_tab);

  const hasMultipleSources = (result.all_web_results?.length ?? 0) > 1;
  const views = hasMultipleSources ? [...VIEWS, { key: "sources", label: "📋 切換來源" }] : VIEWS;

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div>
          <h2 className="text-lg font-semibold text-detail">
            {result.song.artist ?? "未知歌手"} - {result.song.title ?? "未知歌曲"}
          </h2>
          <p className="text-sm text-detail/60">
            ♩={Math.round(result.bpm || 0)} {result.key ? `· 調：${result.key}` : ""}
          </p>
        </div>
        <div className="flex items-center gap-2">
          {result.suggested_capo > 0 && (
            <span className="inline-flex items-center gap-1 rounded-full bg-accent/20 px-3 py-1 text-sm font-medium text-accent">
              🎸 Capo {result.suggested_capo}
            </span>
          )}
          <SourceBadge tab={activeTab} />
        </div>
      </div>

      {result.warnings?.length > 0 && (
        <div className="rounded-lg border border-accent/40 bg-accent/10 p-3 text-sm text-accent">
          {result.warnings.map((w, i) => (
            <div key={i}>⚠ {w}</div>
          ))}
        </div>
      )}

      <div className="flex gap-2 border-b border-detail/10">
        {views.map((v) => (
          <button
            key={v.key}
            type="button"
            onClick={() => setView(v.key)}
            className={`px-3 py-2 text-sm font-medium transition-colors ${
              view === v.key
                ? "border-b-2 border-accent text-accent"
                : "text-detail/60 hover:text-detail"
            }`}
          >
            {v.label}
          </button>
        ))}
      </div>

      <div className="min-h-[200px]">
        {view === "tab" && (
          <pre className="overflow-x-auto rounded-lg bg-black/30 p-4 font-tab text-sm leading-relaxed text-detail">
            {activeTab.ascii}
          </pre>
        )}
        {view === "chords" && <ChordGrid chordInfo={result.chord_info} />}
        {view === "timeline" && (
          <div className="space-y-4">
            {result.measures?.length > 0 ? (
              <MeasureGrid measures={result.measures} />
            ) : (
              <>
                <ChordTimeline chords={result.chords} />
                <StrumPattern strums={result.strum_pattern} />
              </>
            )}
          </div>
        )}
        {view === "sources" && (
          <div className="space-y-2">
            {result.all_web_results.map((tab, i) => (
              <button
                key={i}
                type="button"
                onClick={() => {
                  setActiveTab(tab);
                  setView("tab");
                }}
                className={`flex w-full items-center justify-between rounded-lg border p-3 text-left transition-colors ${
                  activeTab === tab ? "border-accent bg-accent/10" : "border-detail/10 hover:border-detail/30"
                }`}
              >
                <SourceBadge tab={tab} />
                <span className="text-xs text-detail/50">score {Math.round(tab.score)}</span>
              </button>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
