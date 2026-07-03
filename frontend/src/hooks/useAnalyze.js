import { useCallback, useRef, useState } from "react";

const SSE_EVENT_SEP = "\n\n";

async function* readSSEStream(response) {
  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    let sepIndex;
    while ((sepIndex = buffer.indexOf(SSE_EVENT_SEP)) !== -1) {
      const rawEvent = buffer.slice(0, sepIndex);
      buffer = buffer.slice(sepIndex + SSE_EVENT_SEP.length);
      const line = rawEvent.split("\n").find((l) => l.startsWith("data:"));
      if (!line) continue;
      try {
        yield JSON.parse(line.slice(5).trim());
      } catch {
        // 忽略格式不完整的事件
      }
    }
  }
}

/** SSE 分析流程的共用 state machine：idle -> running -> done | error。
 * 用 fetch + ReadableStream 手動解析 SSE，而不是原生 EventSource，
 * 因為上傳檔案那個 endpoint 是 POST + multipart/form-data，
 * EventSource 不支援自訂 method/body。*/
export default function useAnalyze() {
  const [status, setStatus] = useState("idle");
  const [events, setEvents] = useState([]);
  const [result, setResult] = useState(null);
  const [error, setError] = useState(null);
  const abortRef = useRef(null);

  const reset = useCallback(() => {
    setStatus("idle");
    setEvents([]);
    setResult(null);
    setError(null);
  }, []);

  const _consume = useCallback(async (responsePromise) => {
    setStatus("running");
    setEvents([]);
    setResult(null);
    setError(null);
    try {
      const response = await responsePromise;
      if (!response.ok) {
        const text = await response.text().catch(() => "");
        setStatus("error");
        setError({ message: text || `HTTP ${response.status}` });
        return;
      }
      for await (const evt of readSSEStream(response)) {
        setEvents((prev) => [...prev, evt]);
        if (evt.step === "error") {
          setStatus("error");
          setError(evt);
          return;
        }
        if (evt.step === "done") {
          setResult(evt.data?.result ?? null);
          setStatus("done");
          return;
        }
      }
      setStatus("error");
      setError({ message: "連線中斷，沒有收到結束事件" });
    } catch (err) {
      if (err.name !== "AbortError") {
        setStatus("error");
        setError({ message: err.message });
      }
    }
  }, []);

  const analyzeUrl = useCallback(
    (url, mode) => {
      const controller = new AbortController();
      abortRef.current = controller;
      const qs = new URLSearchParams({ url, mode });
      return _consume(
        fetch(`/api/analyze/stream?${qs.toString()}`, { signal: controller.signal })
      );
    },
    [_consume]
  );

  const analyzeFile = useCallback(
    (file, mode) => {
      const controller = new AbortController();
      abortRef.current = controller;
      const form = new FormData();
      form.append("file", file);
      const qs = new URLSearchParams({ mode });
      return _consume(
        fetch(`/api/analyze/file/stream?${qs.toString()}`, {
          method: "POST",
          body: form,
          signal: controller.signal,
        })
      );
    },
    [_consume]
  );

  const cancel = useCallback(() => {
    abortRef.current?.abort();
    setStatus("idle");
  }, []);

  return { status, events, result, error, analyzeUrl, analyzeFile, cancel, reset };
}
