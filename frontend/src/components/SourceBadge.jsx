const SOURCE_LABELS = {
  "91pu": "91譜",
  "91jtp": "91jtp",
  gprotab: "GProTab.net",
  guitarprotabs: "GuitarProTabs.org",
  songsterr: "Songsterr",
  ultimate_guitar: "Ultimate Guitar",
  chordie: "Chordie",
  ai_analysis: "AI 自動生成",
};

const TAB_TYPE_LABELS = {
  guitar_pro: "Guitar Pro",
  full_tab: "完整譜",
  chords: "和弦譜",
  ai: "AI 自動生成",
};

export default function SourceBadge({ tab }) {
  if (!tab) return null;
  const sourceLabel = SOURCE_LABELS[tab.source] ?? tab.source;
  const typeLabel = TAB_TYPE_LABELS[tab.tab_type] ?? tab.tab_type;

  if (tab.tab_type === "ai") {
    return (
      <span className="inline-flex items-center gap-1.5 rounded-full bg-detail/10 px-3 py-1 text-sm text-detail/90">
        🤖 {sourceLabel} · 準確度約 70-80%
      </span>
    );
  }

  const icon = tab.tab_type === "guitar_pro" ? "🏆" : "🌐";

  return (
    <span className="inline-flex items-center gap-1.5 rounded-full bg-detail/10 px-3 py-1 text-sm text-detail/90">
      {icon} {typeLabel} · {sourceLabel}
      {tab.rating != null && <span className="text-accent">⭐{tab.rating.toFixed(1)}</span>}
    </span>
  );
}
