function formatTime(t) {
  const m = Math.floor(t / 60);
  const s = Math.floor(t % 60)
    .toString()
    .padStart(2, "0");
  return `${m}:${s}`;
}

export default function ChordTimeline({ chords }) {
  if (!chords?.length) {
    return <p className="text-detail/60 text-sm">沒有和弦時間軸資料。</p>;
  }

  const withDuration = chords.map((c, i) => {
    const next = chords[i + 1];
    const duration = next ? next.time - c.time : 4;
    return { ...c, duration: Math.max(duration, 1) };
  });
  const totalDuration = withDuration.reduce((sum, c) => sum + c.duration, 0) || 1;

  return (
    <div className="space-y-2">
      <div className="flex h-16 w-full overflow-hidden rounded-lg border border-detail/20">
        {withDuration.map((c, i) => (
          <div
            key={i}
            style={{ flexGrow: c.duration / totalDuration }}
            title={`${formatTime(c.time)} · ${c.chord}`}
            className="flex min-w-[3rem] items-center justify-center border-r border-bg/40 bg-accent/20 font-tab text-sm text-detail transition-colors last:border-r-0 hover:bg-accent/40"
          >
            {c.chord}
          </div>
        ))}
      </div>
      <div className="flex justify-between font-tab text-xs text-detail/50">
        <span>{formatTime(chords[0].time)}</span>
        <span>{formatTime(chords[chords.length - 1].time)}</span>
      </div>
    </div>
  );
}
