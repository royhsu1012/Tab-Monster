function Line({ event }) {
  const isError = event.step === "error";
  const isDone = event.step === "done";
  const icon = isError ? "❌" : isDone ? "✅" : "⏳";
  return (
    <div className={`flex gap-2 text-sm ${isError ? "text-red-400" : "text-detail/80"}`}>
      <span>{icon}</span>
      <span className="font-tab">{event.message}</span>
    </div>
  );
}

export default function ProgressLog({ events, mode }) {
  if (!events.length) return null;

  const searchEvents = events.filter((e) => e.step.startsWith("search"));
  const aiEvents = events.filter((e) => e.step.startsWith("ai") || e.step.startsWith("generate"));
  const otherEvents = events.filter(
    (e) => !e.step.startsWith("search") && !e.step.startsWith("ai") && !e.step.startsWith("generate")
  );

  const showSplit = mode === "parallel" && (searchEvents.length > 0 || aiEvents.length > 0);

  return (
    <div className="space-y-3 rounded-lg border border-detail/10 bg-black/20 p-4">
      <div className="space-y-1">
        {otherEvents.map((e, i) => (
          <Line key={`o-${i}`} event={e} />
        ))}
      </div>

      {showSplit ? (
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 pt-2 border-t border-detail/10">
          <div className="space-y-1">
            <div className="text-xs uppercase tracking-wide text-accent mb-1">🌐 網路搜尋</div>
            {searchEvents.map((e, i) => (
              <Line key={`s-${i}`} event={e} />
            ))}
          </div>
          <div className="space-y-1">
            <div className="text-xs uppercase tracking-wide text-accent mb-1">🤖 AI 分析</div>
            {aiEvents.map((e, i) => (
              <Line key={`a-${i}`} event={e} />
            ))}
          </div>
        </div>
      ) : (
        <div className="space-y-1">
          {[...searchEvents, ...aiEvents].map((e, i) => (
            <Line key={`m-${i}`} event={e} />
          ))}
        </div>
      )}
    </div>
  );
}
