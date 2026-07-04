const PX_PER_SECOND = 40;

/** 刷弦方向（↓/↑）是依「正拍下刷、反拍上刷」的慣例推論出來的，不是從音色
 * 直接判斷出下刷/上刷（目前沒有可靠的音訊技術能做到），所以標題明講是推論。 */
export default function StrumPattern({ strums }) {
  if (!strums?.length) {
    return <p className="text-sm text-detail/60">沒有偵測到刷弦節奏。</p>;
  }

  const totalTime = strums[strums.length - 1].time || 1;
  const width = Math.max(totalTime * PX_PER_SECOND, 200);

  return (
    <div className="space-y-1">
      <p className="text-xs text-detail/50">
        🎸 刷弦節奏（推論：正拍下刷 ↓・反拍上刷 ↑，非音色偵測）
      </p>
      <div className="overflow-x-auto rounded-lg border border-detail/20 bg-black/20">
        <div className="relative h-10" style={{ width: `${width}px` }}>
          {strums.map((s, i) => (
            <span
              key={i}
              style={{ left: `${(s.time / totalTime) * 100}%` }}
              title={`${s.time.toFixed(2)}s`}
              className="absolute top-1/2 -translate-x-1/2 -translate-y-1/2 font-tab text-base text-accent"
            >
              {s.direction === "down" ? "↓" : "↑"}
            </span>
          ))}
        </div>
      </div>
    </div>
  );
}
