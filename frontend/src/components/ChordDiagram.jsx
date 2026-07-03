const FRETS = 5;
const STRINGS = 6;
const STRING_GAP = 16;
const FRET_GAP = 18;
const ORIGIN_X = 20;
const ORIGIN_Y = 20;

const stringX = (i) => ORIGIN_X + i * STRING_GAP;
const fretY = (i) => ORIGIN_Y + i * FRET_GAP;

/** SVG 指板圖，5品x6弦。fingering 陣列順序是 [E,A,D,G,B,e]（低音到高音），
 * 剛好對應標準和弦圖由左到右畫低音弦到高音弦的慣例，不用反轉。 */
export default function ChordDiagram({ chordInfo }) {
  if (!chordInfo) return null;
  const { chord, fingering, barre_fret: barreFret } = chordInfo;

  const positiveFrets = fingering.filter((f) => f > 0);
  const maxFret = positiveFrets.length ? Math.max(...positiveFrets) : 0;
  const startFret = maxFret > FRETS ? maxFret - FRETS + 1 : 1;

  return (
    <div className="inline-flex flex-col items-center gap-1">
      <div className="font-ui font-semibold text-detail">{chord}</div>
      <svg width={140} height={140} viewBox="0 0 140 140">
        {startFret === 1 ? (
          <rect x={ORIGIN_X} y={ORIGIN_Y - 3} width={STRING_GAP * (STRINGS - 1)} height={4} fill="#C8C8C0" />
        ) : (
          <text x={2} y={ORIGIN_Y + 4} fontSize={10} fill="#C8C8C0">
            {startFret}fr
          </text>
        )}

        {Array.from({ length: FRETS + 1 }).map((_, i) => (
          <line
            key={`f${i}`}
            x1={ORIGIN_X}
            y1={fretY(i)}
            x2={ORIGIN_X + STRING_GAP * (STRINGS - 1)}
            y2={fretY(i)}
            stroke="#C8C8C0"
            strokeOpacity={0.4}
          />
        ))}
        {Array.from({ length: STRINGS }).map((_, i) => (
          <line
            key={`s${i}`}
            x1={stringX(i)}
            y1={ORIGIN_Y}
            x2={stringX(i)}
            y2={fretY(FRETS)}
            stroke="#C8C8C0"
            strokeOpacity={0.4}
          />
        ))}

        {barreFret != null && (
          <line
            x1={stringX(0)}
            y1={fretY(barreFret - startFret) + FRET_GAP / 2}
            x2={stringX(STRINGS - 1)}
            y2={fretY(barreFret - startFret) + FRET_GAP / 2}
            stroke="#D4870A"
            strokeWidth={6}
            strokeLinecap="round"
          />
        )}

        {fingering.map((f, i) => {
          const x = stringX(i);
          if (f === -1) {
            return (
              <text key={i} x={x} y={ORIGIN_Y - 8} fontSize={10} textAnchor="middle" fill="#C8C8C0">
                ×
              </text>
            );
          }
          if (f === 0) {
            return (
              <circle key={i} cx={x} cy={ORIGIN_Y - 8} r={4} fill="none" stroke="#C8C8C0" strokeWidth={1.5} />
            );
          }
          const fretIdx = f - startFret;
          if (fretIdx < 0 || fretIdx >= FRETS) return null;
          return <circle key={i} cx={x} cy={fretY(fretIdx) + FRET_GAP / 2} r={5} fill="#D4870A" />;
        })}
      </svg>
    </div>
  );
}
