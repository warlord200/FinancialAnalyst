import { useState } from "react";
import { chatStep } from "../api";
import type { ChatSource } from "../api";

export interface ChatMessage {
  role: "user" | "assistant";
  text: string;
  sources?: ChatSource[];
  evidence?: string[];
  error?: string;
}

export function ChatPanel({
  ticker,
  step,
  label,
}: {
  ticker: string;
  step: number;
  label: string;
}) {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState("");
  const [searchAll, setSearchAll] = useState(false);
  const [busy, setBusy] = useState(false);

  async function send() {
    const question = input.trim();
    if (!question || busy) return;
    setBusy(true);
    setInput("");
    setMessages((prev) => [...prev, { role: "user", text: question }]);
    try {
      const res = await chatStep(ticker, step, question, searchAll);
      setMessages((prev) => [
        ...prev,
        {
          role: "assistant",
          text: res.answer,
          sources: res.sources,
          evidence: res.evidence,
        },
      ]);
    } catch (e) {
      setMessages((prev) => [
        ...prev,
        {
          role: "assistant",
          text: "",
          error: e instanceof Error ? e.message : "Chat failed",
        },
      ]);
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="chat-panel">
      <div className="panel-title">
        <span>Ask this dossier</span>
        <label className="chat-search-all">
          <input
            type="checkbox"
            checked={searchAll}
            onChange={(e) => setSearchAll(e.target.checked)}
          />
          Search everything
        </label>
      </div>
      <p className="step-scope" style={{ marginBottom: 2 }}>
        Chat · {label} · scoped to this step's source material
      </p>
      <div className="chat-log">
        {messages.length === 0 && (
          <p className="empty-copy">Ask a question about this step's source material.</p>
        )}
        {messages.map((m, i) => (
          <div key={i} className={`chat-msg chat-${m.role}`}>
            <span className="chat-role">{m.role === "user" ? "You" : "Assistant"}</span>
            {m.error ? (
              <div className="error-banner">{m.error}</div>
            ) : (
              <p className="chat-text">{m.text}</p>
            )}
            {m.sources && m.sources.length > 0 && (
              <div className="source-tags">
                {m.sources.map((s, j) => (
                  <span key={j} className="source-tag source-item">
                    {s.item ? `${s.item} · ` : ""}
                    {s.fiscal_year ? `FY${s.fiscal_year} · ` : ""}
                    {s.filing ?? "10-K"}
                  </span>
                ))}
              </div>
            )}
            {m.evidence && m.evidence.length > 0 && (
              <details className="evidence-block">
                <summary>Source quotes</summary>
                <ul>
                  {m.evidence.map((quote, j) => (
                    <li key={j}>"{quote}"</li>
                  ))}
                </ul>
              </details>
            )}
          </div>
        ))}
      </div>
      <div className="chat-input-row">
        <input
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && send()}
          placeholder={`Ask about ${ticker}…`}
          className="text-input"
        />
        <button onClick={send} disabled={busy || !input.trim()} className="btn btn-primary">
          Send
        </button>
      </div>
    </section>
  );
}
