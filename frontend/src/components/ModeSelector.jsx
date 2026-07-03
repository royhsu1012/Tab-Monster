const MODES = [
  {
    value: "web_first",
    icon: "🌐",
    label: "搜譜優先",
    desc: "先找網路譜，找不到再 AI",
    eta: "~15s",
  },
  {
    value: "parallel",
    icon: "⚡",
    label: "並行模式",
    desc: "同時搜尋+AI，取最佳",
    eta: "~60s",
    recommended: true,
  },
  {
    value: "ai_only",
    icon: "🤖",
    label: "AI 分析",
    desc: "直接音訊分析，不搜網路",
    eta: "~45s",
  },
];

export default function ModeSelector({ value, onChange, disabled }) {
  return (
    <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
      {MODES.map((mode) => {
        const selected = value === mode.value;
        return (
          <button
            key={mode.value}
            type="button"
            disabled={disabled}
            onClick={() => onChange(mode.value)}
            className={`text-left rounded-lg border p-4 transition-colors disabled:opacity-50 disabled:cursor-not-allowed ${
              selected
                ? "border-accent bg-accent/10"
                : "border-detail/20 hover:border-detail/40"
            }`}
          >
            <div className="flex items-center justify-between">
              <span className="text-xl">{mode.icon}</span>
              {mode.recommended && (
                <span className="text-[10px] uppercase tracking-wide bg-accent text-bg px-1.5 py-0.5 rounded">
                  推薦
                </span>
              )}
            </div>
            <div className="mt-2 font-ui font-semibold text-detail">{mode.label}</div>
            <div className="mt-1 text-sm text-detail/70">{mode.desc}</div>
            <div className="mt-2 text-xs text-accent">{mode.eta}</div>
          </button>
        );
      })}
    </div>
  );
}
