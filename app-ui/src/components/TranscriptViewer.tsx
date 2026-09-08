import { useEffect, useMemo, useRef, useState } from "react";
import { getTranscriptSnapshot } from "../services/api";

interface TranscriptViewerProps {
  title?: string;
  pollIntervalMs?: number;
  /** 实时字幕：正在说但还没落盘的那句（空串表示无） */
  livePartial?: string;
}

export default function TranscriptViewer({
  title = "课堂转录记录",
  pollIntervalMs = 5000,
  livePartial = "",
}: TranscriptViewerProps) {
  const [content, setContent] = useState("");
  const [mtime, setMtime] = useState<number | null>(null);
  const [lineCount, setLineCount] = useState(0);
  const [autoFollow, setAutoFollow] = useState(true);
  const [error, setError] = useState("");
  const scrollRef = useRef<HTMLDivElement | null>(null);

  const pullSnapshot = async () => {
    try {
      const res = await getTranscriptSnapshot(mtime ?? undefined);
      if (!res.exists) {
        setContent("");
        setLineCount(0);
        setError("");
        return;
      }
      setError("");
      if (res.changed) {
        setContent(res.content || "");
        setLineCount(res.line_count || 0);
      }
      if (res.mtime !== null) {
        setMtime(res.mtime);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "拉取转录失败");
    }
  };

  useEffect(() => {
    pullSnapshot();
    const timer = window.setInterval(() => {
      pullSnapshot();
    }, pollIntervalMs);
    return () => window.clearInterval(timer);
  }, [pollIntervalMs]);

  useEffect(() => {
    if (!autoFollow || !scrollRef.current) return;
    scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
  }, [content, autoFollow, livePartial]);

  const summaryText = useMemo(() => {
    if (!content.trim()) {
      return "暂无转录内容";
    }
    return `${lineCount} 行`;
  }, [content, lineCount]);

  return (
    <div className="flex h-full min-h-0 flex-col rounded-2xl border border-white/10 bg-white/6 p-3">
      <div className="mb-2 flex items-center justify-between gap-2">
        <div>
          <div className="text-xs font-semibold text-white/85">{title}</div>
          <div className="text-[11px] text-white/45">{summaryText}</div>
        </div>
        <button
          onClick={() => setAutoFollow((prev) => !prev)}
          className={`rounded-lg border px-2.5 py-1 text-[11px] transition ${
            autoFollow
              ? "border-cyan-400/25 bg-cyan-500/15 text-cyan-100"
              : "border-white/15 bg-white/8 text-white/70"
          }`}
        >
          {autoFollow ? "自动跟随" : "手动滚动"}
        </button>
      </div>

      {error && (
        <div className="mb-2 rounded-lg border border-red-500/30 bg-red-500/12 px-2 py-1 text-[11px] text-red-300">
          {error}
        </div>
      )}

      <div
        ref={scrollRef}
        className="min-h-0 flex-1 overflow-y-auto rounded-xl border border-white/10 bg-black/20 p-2 text-[11px] leading-5 text-white/78"
      >
        <pre className="whitespace-pre-wrap break-words font-mono">{content || "（等待课堂转录中...）"}</pre>
        {livePartial && (
          <div className="mt-1 flex items-start gap-1.5 rounded-lg border border-cyan-400/25 bg-cyan-500/10 px-2 py-1">
            <span className="mt-[2px] inline-block h-1.5 w-1.5 shrink-0 animate-pulse rounded-full bg-cyan-300" />
            <span className="break-words font-mono text-cyan-100/85">{livePartial}</span>
          </div>
        )}
      </div>
    </div>
  );
}
