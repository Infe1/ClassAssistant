import { useEffect, useMemo, useState } from "react";
import {
  catchupChat,
  catchupWithPrompt,
  emergencyRescueChat,
  emergencyRescueWithPrompt,
} from "../services/api";
import MarkdownRenderer from "./MarkdownRenderer";

type ChatMode = "catchup" | "rescue";

interface InlineAIChatProps {
  visible: boolean;
  mode: ChatMode;
}

interface RescueSeed {
  context: string;
  question: string;
  answer: string;
}

export default function InlineAIChat({ visible, mode }: InlineAIChatProps) {
  const [loading, setLoading] = useState(false);
  const [asking, setAsking] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [summary, setSummary] = useState("");
  const [rescueSeed, setRescueSeed] = useState<RescueSeed | null>(null);
  const [question, setQuestion] = useState("");
  const [messages, setMessages] = useState<Array<{ role: "user" | "assistant"; content: string }>>([]);

  const titleText = mode === "catchup" ? "AI 进度对话" : "AI 救场对话";
  const placeholder =
    mode === "catchup"
      ? "问：老师刚才提到的术语是什么意思？"
      : "问：如果老师继续追问，我怎么简洁回答？";

  const canAsk = useMemo(() => !!question.trim() && !asking && !loading, [question, asking, loading]);

  const bootstrap = async () => {
    setLoading(true);
    setError(null);
    setQuestion("");
    setMessages([]);
    try {
      if (mode === "catchup") {
        const res = await catchupWithPrompt({});
        setSummary(res.summary || "");
        setRescueSeed(null);
      } else {
        const res = await emergencyRescueWithPrompt({});
        setRescueSeed({
          context: res.context,
          question: res.question,
          answer: res.answer,
        });
        setSummary("");
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "获取 AI 上下文失败");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (!visible) return;
    bootstrap();
  }, [visible, mode]);

  if (!visible) return null;

  const handleAsk = async () => {
    const input = question.trim();
    if (!input || asking) return;

    setAsking(true);
    setError(null);
    setQuestion("");
    const history = [...messages, { role: "user" as const, content: input }];
    setMessages(history);

    try {
      if (mode === "catchup") {
        const res = await catchupChat({
          summary,
          question: input,
          history: messages,
        });
        setMessages((prev) => [...prev, { role: "assistant", content: res.answer }]);
      } else {
        if (!rescueSeed) throw new Error("救场上下文未准备好");
        const res = await emergencyRescueChat({
          context: rescueSeed.context,
          question: rescueSeed.question,
          answer: rescueSeed.answer,
          followup: input,
          history: messages,
        });
        setMessages((prev) => [...prev, { role: "assistant", content: res.answer }]);
      }
    } catch (err) {
      // 追问失败时把问题放回输入框：`asking` 已解锁，用户可以直接重发，
      // 不必重新敲一遍（超时场景下这一点很关键）。
      setQuestion(input);
      setError(err instanceof Error ? err.message : "追问失败");
    } finally {
      setAsking(false);
    }
  };

  /** 重试上一次提问：把问题填回输入框并立即重发。 */
  const handleRetry = () => {
    const lastUser = [...messages].reverse().find((item) => item.role === "user");
    if (!lastUser) return;
    setQuestion(lastUser.content);
    setError(null);
  };

  return (
    <div className="flex h-full min-h-0 flex-col rounded-2xl border border-white/10 bg-white/6 p-3">
      <div className="mb-2 flex items-center justify-between">
        <span className="text-xs font-semibold text-white/88">{titleText}</span>
        <button
          onClick={bootstrap}
          className="rounded-lg border border-cyan-400/20 bg-cyan-500/12 px-2 py-1 text-[11px] text-cyan-100 transition hover:bg-cyan-500/20"
        >
          刷新
        </button>
      </div>

      {loading && <div className="mb-2 shrink-0 text-xs text-white/60">正在加载 AI 上下文...</div>}
      {error && (
        <div className="mb-2 flex shrink-0 items-center gap-2 rounded-lg border border-red-500/30 bg-red-500/12 px-2 py-1 text-xs text-red-200">
          <span className="min-w-0 flex-1 break-words">{error}</span>
          {messages.length > 0 && (
            <button
              onClick={handleRetry}
              className="shrink-0 rounded-md border border-red-400/30 bg-red-500/16 px-2 py-0.5 text-[11px] text-red-100 transition hover:bg-red-500/24"
            >
              重填
            </button>
          )}
        </div>
      )}

      <div className="min-h-0 flex-1 overflow-y-auto rounded-xl border border-white/10 bg-black/20 p-2">
        {!loading && mode === "catchup" && summary && (
          <div className="mb-2 rounded-xl border border-indigo-400/20 bg-indigo-500/10 p-2">
            <MarkdownRenderer content={summary} />
          </div>
        )}

        {!loading && mode === "rescue" && rescueSeed && (
          <div className="mb-2 rounded-xl border border-emerald-400/20 bg-emerald-500/10 p-2">
            <MarkdownRenderer
              content={`**课堂上下文**\n${rescueSeed.context}\n\n**老师问题**\n${rescueSeed.question}\n\n**建议答案**\n${rescueSeed.answer}`}
            />
          </div>
        )}

        {messages.length === 0 ? (
          <div className="text-xs text-white/45">可以开始追问，回答支持 Markdown 与公式渲染。</div>
        ) : (
          <div className="flex flex-col gap-2">
            {messages.map((item, idx) => (
              <div
                key={`${item.role}-${idx}`}
                className={`rounded-xl px-2 py-1.5 text-xs ${
                  item.role === "user"
                    ? "self-end bg-cyan-500/16 text-cyan-50"
                    : "self-start border border-white/10 bg-white/7 text-white/88"
                }`}
              >
                <MarkdownRenderer content={item.content} />
              </div>
            ))}
            {asking && <div className="text-xs text-white/55">AI 思考中...</div>}
          </div>
        )}
      </div>

      <div className="mt-2 flex shrink-0 items-stretch gap-2">
        <textarea
          value={question}
          onChange={(e) => setQuestion(e.target.value)}
          placeholder={placeholder}
          className="h-14 flex-1 resize-none rounded-xl border border-white/10 bg-black/15 px-2 py-1.5 text-xs text-white outline-none transition focus:border-cyan-400/50"
        />
        <button
          onClick={handleAsk}
          disabled={!canAsk}
          className="rounded-xl border border-cyan-400/20 bg-cyan-500/16 px-3 text-xs font-medium text-cyan-100 transition hover:bg-cyan-500/24 disabled:opacity-50"
        >
          追问
        </button>
      </div>
    </div>
  );
}
