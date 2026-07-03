import { useState } from "react";
import InputPanel from "./components/InputPanel.jsx";
import ModeSelector from "./components/ModeSelector.jsx";
import ProgressLog from "./components/ProgressLog.jsx";
import TabDisplay from "./components/TabDisplay.jsx";
import useAnalyze from "./hooks/useAnalyze.js";

export default function App() {
  const [mode, setMode] = useState("parallel");
  const { status, events, result, error, analyzeUrl, analyzeFile, reset } = useAnalyze();

  const running = status === "running";

  const handleStart = ({ type, value }) => {
    reset();
    if (type === "url") {
      analyzeUrl(value, mode);
    } else {
      analyzeFile(value, mode);
    }
  };

  return (
    <div className="min-h-screen bg-bg text-detail">
      <div className="mx-auto max-w-3xl space-y-8 px-4 py-10">
        <header className="space-y-1 text-center">
          <h1 className="text-3xl font-bold text-detail">🎸👾 TabMonster</h1>
          <p className="text-detail/60">Feed it a song. Get a tab.</p>
        </header>

        <InputPanel onStart={handleStart} disabled={running} />

        <div>
          <h3 className="mb-2 text-sm font-semibold text-detail/70">分析模式</h3>
          <ModeSelector value={mode} onChange={setMode} disabled={running} />
        </div>

        {(running || events.length > 0) && (
          <div>
            <h3 className="mb-2 text-sm font-semibold text-detail/70">進度</h3>
            <ProgressLog events={events} mode={mode} />
          </div>
        )}

        {status === "error" && error && (
          <div className="rounded-lg border border-red-500/40 bg-red-500/10 p-4 text-red-300">
            ❌ {error.data?.code ? `[${error.data.code}] ` : ""}
            {error.message}
          </div>
        )}

        {status === "done" && result && (
          <div>
            <h3 className="mb-2 text-sm font-semibold text-detail/70">結果</h3>
            <TabDisplay result={result} />
          </div>
        )}
      </div>
    </div>
  );
}
