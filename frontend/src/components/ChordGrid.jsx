import ChordDiagram from "./ChordDiagram.jsx";

export default function ChordGrid({ chordInfo }) {
  if (!chordInfo?.length) {
    return <p className="text-detail/60 text-sm">沒有偵測到和弦資料。</p>;
  }
  return (
    <div className="flex flex-wrap gap-4">
      {chordInfo.map((info) => (
        <ChordDiagram key={info.chord} chordInfo={info} />
      ))}
    </div>
  );
}
