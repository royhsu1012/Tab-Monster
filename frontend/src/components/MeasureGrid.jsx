const SLOT_SYMBOL = { down: "↓", up: "↑" };

/** 以小節為單位顯示和弦+刷弦節奏，像真正的和弦譜一樣有小節框，比攤平的
 * 時間軸好讀。小節假設 4/4 拍（本專案不偵測拍號），第一小節的起點是抓拍
 * 演算法偵測到的第一個拍子，不一定跟原曲真正的小節對齊，但小節長度是準的。 */
export default function MeasureGrid({ measures }) {
  if (!measures?.length) {
    return <p className="text-sm text-detail/60">沒有小節資料。</p>;
  }

  return (
    <div className="space-y-2">
      <p className="text-xs text-detail/50">
        每格代表一個小節（4/4 拍），上面是和弦、下面是刷弦節奏（↓ 正拍下刷・↑ 反拍上刷・推論非偵測）
      </p>
      <div className="grid grid-cols-2 gap-2 sm:grid-cols-4 lg:grid-cols-8">
        {measures.map((m) => (
          <div
            key={m.index}
            title={`小節 ${m.index + 1} · ${m.start_time.toFixed(1)}s`}
            className="rounded-lg border border-detail/20 bg-black/20 p-2"
          >
            <div className="mb-1.5 text-center font-tab text-sm font-semibold text-accent">
              {m.chord ?? "–"}
            </div>
            <div className="flex justify-between font-tab text-sm">
              {m.strums.map((s, i) => (
                <span key={i} className={s ? "text-detail" : "text-detail/20"}>
                  {s ? SLOT_SYMBOL[s] : "·"}
                </span>
              ))}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
