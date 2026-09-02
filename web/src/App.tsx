import { useCallback, useEffect, useState } from "react";
import {
  chatStep,
  clearPeers,
  clearPriceOverride,
  getBusinessSwot,
  getFinancials,
  getIngestJob,
  getIngestStats,
  getMe,
  getNumbers,
  getOnePager,
  getPeers,
  getQuota,
  getStrategy,
  getToken,
  ingestTicker,
  listIngested,
  login,
  logout,
  refreshNumbers,
  setPeers,
  setPriceOverride,
  setStepGate,
  setToken,
  signup,
  AuthUser,
  BusinessSwotResponse,
  ArtifactSection as ArtifactSectionData,
  ChatSource,
  FinancialsResponse,
  FinancialTable,
  IngestJob,
  IngestedTicker,
  IngestStats,
  NumbersResponse,
  OnePagerResponse,
  QuotaStatus,
  SourceTag,
  StrategyResponse,
  TableUnit,
} from "./api";

type Phase = "idle" | "ingesting" | "done" | "error";
type View = "ingest" | "step1" | "step2" | "step3" | "step4" | "step5" | "step6" | "numbers";

const DOSSIER_STEPS = [
  { n: 1, label: "One-pager", view: "step1" as View },
  { n: 2, label: "Business & SWOT", view: "step2" as View },
  { n: 3, label: "Financials", view: "step3" as View },
  { n: 4, label: "Strategy", view: "step4" as View },
  { n: 5, label: "Valuation", view: "step5" as View },
  { n: 6, label: "Thesis", view: "step6" as View },
];

function ChunkTable({ title, rows }: { title: string; rows: [string, number][] }) {
  return (
    <>
      <h2>{title}</h2>
      <table>
        <thead>
          <tr>
            <th>Item</th>
            <th>Chunks</th>
          </tr>
        </thead>
        <tbody>
          {rows.map(([label, count]) => (
            <tr key={label}>
              <td>{label}</td>
              <td>{count}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </>
  );
}

function formatMoney(value: number) {
  const abs = Math.abs(value);
  if (abs >= 1e9) return `$${(value / 1e9).toFixed(2)}B`;
  if (abs >= 1e6) return `$${(value / 1e6).toFixed(1)}M`;
  return `$${value.toLocaleString(undefined, { maximumFractionDigits: 1 })}`;
}

function formatPercent(value: number) {
  return `${(value * 100).toFixed(1)}%`;
}

function MatrixTable({
  title,
  matrix,
  years,
  format,
  yearLabel,
}: {
  title: string;
  matrix: Record<string, Record<string, number>>;
  years?: string[];
  format?: (value: number) => string;
  yearLabel?: (key: string) => string;
}) {
  const rows = Object.entries(matrix).sort(([a], [b]) => a.localeCompare(b));
  if (rows.length === 0) return null;
  const columns =
    years ??
    [...new Set(rows.flatMap(([, byYear]) => Object.keys(byYear)))].sort().reverse();
  return (
    <section className="matrix-block">
      <h2>{title}</h2>
      <table className="matrix">
        <thead>
          <tr>
            <th className="row-label">Line</th>
            {columns.map((column) => (
              <th key={column}>{yearLabel ? yearLabel(column) : column}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map(([label, byYear]) => (
            <tr key={label}>
              <td className="row-label">{label}</td>
              {columns.map((column) => {
                const value = byYear[column];
                return (
                  <td key={column}>
                    {value === undefined ? "—" : format ? format(value) : formatMoney(value)}
                  </td>
                );
              })}
            </tr>
          ))}
        </tbody>
      </table>
    </section>
  );
}

function PriceCard({
  ticker,
  numbers,
  onSaved,
}: {
  ticker: string;
  numbers: NumbersResponse;
  onSaved: (updated: NumbersResponse) => void;
}) {
  const [override, setOverride] = useState("");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const price = numbers.price;

  if (!price) {
    return (
      <section className="price-card">
        <h2>Price</h2>
        <p className="meta-text">No price available yet.</p>
      </section>
    );
  }

  async function saveOverride() {
    const parsed = parseFloat(override);
    if (Number.isNaN(parsed) || parsed <= 0) {
      setError("Enter a positive number.");
      return;
    }
    setSaving(true);
    setError("");
    try {
      const updated = await setPriceOverride(ticker, parsed);
      setOverride("");
      onSaved(updated);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to save override");
    } finally {
      setSaving(false);
    }
  }

  async function removeOverride() {
    setSaving(true);
    try {
      onSaved(await clearPriceOverride(ticker));
    } finally {
      setSaving(false);
    }
  }

  return (
    <section className="price-card">
      <h2>Price</h2>
      <p>
        Current: <strong>${price.effective.price.toFixed(2)}</strong>{" "}
        <span className="meta-text">
          ({price.effective.source === "override" ? "manual override" : "yahoo finance"})
        </span>
      </p>
      {price.override && (
        <p className="meta-text">
          Override ${price.override.price.toFixed(2)} set {price.override.set_at.slice(0, 10)}.{" "}
          <button onClick={removeOverride} disabled={saving} className="link-button">
            Remove
          </button>
        </p>
      )}
      <div className="override-row">
        <input
          type="number"
          step="0.01"
          min="0"
          value={override}
          onChange={(e) => setOverride(e.target.value)}
          placeholder="Manual price override"
        />
        <button onClick={saveOverride} disabled={saving} className="primary">
          Override
        </button>
      </div>
      {error && <div className="error-banner">{error}</div>}
      {price.history.length > 0 && (
        <p className="meta-text">Price history: {price.history.length} daily points.</p>
      )}
    </section>
  );
}

function MetricRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="metric-row">
      <span className="meta-text">{label}</span>
      <span>{value}</span>
    </div>
  );
}

function OnePagerCard({
  response,
  onGate,
}: {
  response: OnePagerResponse;
  onGate: (decision: "accept" | "reject") => void;
}) {
  const { one_pager: op, gate } = response;
  const pct = (v: number | null) => (v === null ? "n/a" : `${(v * 100).toFixed(1)}%`);
  return (
    <article>
      <div className="report-meta">
        <span className="meta-text">
          Step 1 · one-pager · {response.ticker}
          {op.latest_fiscal_year ? ` · FY${op.latest_fiscal_year}` : ""}
        </span>
        <span className={`verdict verdict-${op.tag.label}`}>{op.tag.label}</span>
        <span className="meta-text">score {op.tag.score}/100</span>
      </div>
      <p className="meta-text">{op.tag.rationale} · {op.source}</p>
      <section className="one-pager-block">
        <h2>Growth</h2>
        <MetricRow
          label="Latest revenue"
          value={op.growth.latest_revenue === null ? "n/a" : formatMoney(op.growth.latest_revenue)}
        />
        <MetricRow label="Revenue growth (YoY)" value={pct(op.growth.revenue_growth_yoy)} />
        <MetricRow label="Revenue CAGR (5y)" value={pct(op.growth.revenue_cagr_5y)} />
      </section>
      <section className="one-pager-block">
        <h2>Profitability</h2>
        <MetricRow label="Gross margin" value={pct(op.profitability.gross_margin)} />
        <MetricRow label="Operating margin" value={pct(op.profitability.operating_margin)} />
        <MetricRow label="Net margin" value={pct(op.profitability.net_margin)} />
      </section>
      <section className="one-pager-block">
        <h2>Debt</h2>
        <MetricRow label="Debt / assets" value={pct(op.debt.debt_to_assets)} />
        <MetricRow label="Debt / equity" value={pct(op.debt.debt_to_equity)} />
      </section>
      <section className="gate-block">
        {gate === null ? (
          <>
            <p className="meta-text">Accept the deep dive or stop the flow.</p>
            <div className="gate-actions">
              <button onClick={() => onGate("accept")} className="primary">
                Accept — deep dive
              </button>
              <button onClick={() => onGate("reject")} className="danger">
                Reject
              </button>
            </div>
          </>
        ) : gate.status === "accepted" ? (
          <p className="meta-text">
            Accepted on {gate.updated_at.slice(0, 10)} — deep dive approved.{" "}
            <button className="link-button" onClick={() => onGate("reject")}>
              Reject instead
            </button>
          </p>
        ) : (
          <p className="meta-text">
            Rejected on {gate.updated_at.slice(0, 10)} — flow stopped.{" "}
            <button className="link-button" onClick={() => onGate("accept")}>
              Accept instead
            </button>
          </p>
        )}
      </section>
    </article>
  );
}

function sourceTagLabel(tag: SourceTag) {
  if (tag.type === "fiscal_year") return `FY${tag.value}`;
  return tag.value;
}

function ArtifactSectionCard({ section }: { section: ArtifactSectionData }) {
  return (
    <section className="artifact-section">
      <h2>{section.heading}</h2>
      <p className="artifact-content">{section.content}</p>
      <div className="source-tags">
        {section.sources.map((tag, i) => (
          <span key={i} className={`source-tag source-${tag.type}`}>
            {sourceTagLabel(tag)}
          </span>
        ))}
      </div>
      {section.evidence.length > 0 && (
        <details className="evidence-block">
          <summary>Source quotes</summary>
          <ul>
            {section.evidence.map((quote, i) => (
              <li key={i}>"{quote}"</li>
            ))}
          </ul>
        </details>
      )}
    </section>
  );
}

function BusinessSwotCard({ response }: { response: BusinessSwotResponse }) {
  const { artifact, cached } = response;
  const factSections = artifact.sections.filter((s) => !s.key.startsWith("swot_"));
  const swotSections = artifact.sections.filter((s) => s.key.startsWith("swot_"));
  return (
    <article>
      <div className="report-meta">
        <span className="meta-text">
          Step 2 · Business & SWOT · {artifact.ticker}
          {artifact.fiscal_year ? ` · FY${artifact.fiscal_year}` : ""} ·{" "}
          {artifact.scope.items.join(", ")}
        </span>
        <span className="meta-text">{cached ? "cached draft" : "freshly drafted"}</span>
      </div>
      {factSections.map((section) => (
        <ArtifactSectionCard key={section.key} section={section} />
      ))}
      <h2 className="swot-heading">SWOT</h2>
      <section className="swot-grid">
        {swotSections.map((section) => (
          <div key={section.key} className={`swot-cell swot-${section.key.replace("swot_", "")}`}>
            <ArtifactSectionCard section={section} />
          </div>
        ))}
      </section>
    </article>
  );
}

function formatTableValue(value: number | null, unit: TableUnit) {
  if (value === null) return "—";
  if (unit === "percent") return formatPercent(value);
  return value.toFixed(2);
}

function FinancialsTableCard({ table }: { table: FinancialTable }) {
  if (table.rows.length === 0) return null;
  const citedFacts = table.rows.flatMap((row) =>
    row.sources.map((tag) => ({ label: row.label, tag }))
  );
  return (
    <section className="matrix-block">
      <h2>{table.title}</h2>
      <table className="matrix">
        <thead>
          <tr>
            <th className="row-label">Line</th>
            {table.columns.map((column) => (
              <th key={column}>{table.column_labels?.[column] ?? column}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {table.rows.map((row) => (
            <tr key={row.label}>
              <td className="row-label">{row.label}</td>
              {table.columns.map((column) => (
                <td key={column}>{formatTableValue(row.values[column] ?? null, table.unit)}</td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
      {citedFacts.length > 0 && (
        <details className="evidence-block">
          <summary>XBRL facts cited</summary>
          <ul>
            {citedFacts.map(({ label, tag }, i) => (
              <li key={i}>
                {label}: {tag.value}
              </li>
            ))}
          </ul>
        </details>
      )}
    </section>
  );
}

function FinancialsCard({ response }: { response: FinancialsResponse }) {
  const { artifact, cached } = response;
  return (
    <article>
      <div className="report-meta">
        <span className="meta-text">
          Step 3 · Financials · {artifact.ticker}
          {artifact.fiscal_year ? ` · FY${artifact.fiscal_year}` : ""} ·{" "}
          {artifact.scope.items.join(", ")}
        </span>
        <span className="meta-text">{cached ? "cached draft" : "freshly drafted"}</span>
      </div>
      {artifact.tables.map((table) => (
        <FinancialsTableCard key={table.key} table={table} />
      ))}
      <h2 className="swot-heading">Forensic note</h2>
      {artifact.sections.map((section) => (
        <ArtifactSectionCard key={section.key} section={section} />
      ))}
    </article>
  );
}

function StrategyCard({ response }: { response: StrategyResponse }) {
  const { artifact, cached } = response;
  return (
    <article>
      <div className="report-meta">
        <span className="meta-text">
          Step 4 · Strategy · {artifact.ticker}
          {artifact.fiscal_year ? ` · FY${artifact.fiscal_year}` : ""} ·{" "}
          {artifact.scope.items.join(", ")}
        </span>
        <span className="meta-text">{cached ? "cached draft" : "freshly drafted"}</span>
      </div>
      {artifact.returns && <FinancialsTableCard table={artifact.returns} />}
      {artifact.sections.map((section) => (
        <ArtifactSectionCard key={section.key} section={section} />
      ))}
    </article>
  );
}

function PeerScorecardPanel({
  ticker,
  onQuotaChange,
}: {
  ticker: string;
  onQuotaChange: () => void;
}) {
  const [peers, setPeersList] = useState<string[]>([]);
  const [scorecard, setScorecard] = useState<FinancialTable[]>([]);
  const [input, setInput] = useState("");
  const [error, setError] = useState("");
  const [loaded, setLoaded] = useState(false);
  const [busy, setBusy] = useState(false);

  const refresh = useCallback(async () => {
    setError("");
    try {
      const res = await getPeers(ticker);
      setPeersList(res.peers);
      setScorecard(res.scorecard);
      setLoaded(true);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load peer scorecard");
    }
  }, [ticker]);

  useEffect(() => {
    setLoaded(false);
    setPeersList([]);
    setScorecard([]);
    refresh();
  }, [refresh]);

  async function save(nextPeers: string[]) {
    setBusy(true);
    setError("");
    try {
      const res = await setPeers(ticker, nextPeers);
      setPeersList(res.peers);
      setScorecard(res.scorecard);
      onQuotaChange();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to save peers");
    } finally {
      setBusy(false);
    }
  }

  function addPeer() {
    const peer = input.trim().toUpperCase();
    if (!peer || busy) return;
    setInput("");
    if (!peers.includes(peer)) {
      save([...peers, peer]);
    }
  }

  return (
    <section className="peer-panel">
      <div className="peer-header">
        <span className="meta-text">Peer scorecard · {ticker} vs its peers</span>
        {loaded && (
          <span className="meta-text">{peers.length} peers</span>
        )}
      </div>
      <div className="peer-add-row">
        <input
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && addPeer()}
          placeholder="Add a peer ticker (e.g. F)"
          className="ticker-input"
        />
        <button onClick={addPeer} disabled={busy || !input.trim()} className="primary">
          Add peer
        </button>
        {peers.length > 0 && (
          <button
            onClick={() => {
              setBusy(true);
              setError("");
              clearPeers(ticker)
                .then((res) => {
                  setPeersList(res.peers);
                  setScorecard(res.scorecard);
                })
                .catch((e) => setError(e instanceof Error ? e.message : "Failed to clear peers"))
                .finally(() => setBusy(false));
            }}
            disabled={busy}
            className="link-button"
          >
            Clear all
          </button>
        )}
      </div>
      {error && <div className="error-banner">{error}</div>}
      {peers.length > 0 && (
        <div className="peer-list">
          {peers.map((peer) => (
            <span key={peer} className="peer-chip">
              {peer}
              <button
                onClick={() => save(peers.filter((p) => p !== peer))}
                disabled={busy}
                className="link-button"
                aria-label={`Remove peer ${peer}`}
              >
                ×
              </button>
            </span>
          ))}
        </div>
      )}
      {scorecard.length > 0 ? (
        scorecard.map((table) => <FinancialsTableCard key={table.key} table={table} />)
      ) : (
        <p className="meta-text">
          Add peer tickers to compare {ticker}'s growth, margins, debt, and returns
          against theirs (latest fiscal year each).
        </p>
      )}
    </section>
  );
}

interface ChatMessage {
  role: "user" | "assistant";
  text: string;
  sources?: ChatSource[];
  evidence?: string[];
  error?: string;
}

function ChatPanel({
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
      <div className="chat-meta">
        <span className="meta-text">
          Chat · {label} · scoped to this step's source material
        </span>
        <label className="chat-search-all">
          <input
            type="checkbox"
            checked={searchAll}
            onChange={(e) => setSearchAll(e.target.checked)}
          />
          Search everything
        </label>
      </div>
      <div className="chat-log">
        {messages.length === 0 && (
          <p className="meta-text">Ask a question about this step's source material.</p>
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
        />
        <button onClick={send} disabled={busy || !input.trim()} className="primary">
          Send
        </button>
      </div>
    </section>
  );
}

function AuthPanel({
  onAuthenticated,
}: {
  onAuthenticated: (user: AuthUser) => void;
}) {
  const [mode, setMode] = useState<"login" | "signup">("login");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  async function submit() {
    if (!email || !password) {
      setError("Enter an email and password.");
      return;
    }
    setBusy(true);
    setError("");
    try {
      const res = mode === "login" ? await login(email, password) : await signup(email, password);
      setToken(res.token);
      onAuthenticated(res.user);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Authentication failed");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="auth-panel">
      <h2>{mode === "login" ? "Log in" : "Create an account"}</h2>
      <p className="meta-text">
        {mode === "signup"
          ? "Accounts work immediately. Unverified accounts get stricter daily quotas."
          : "Log in to analyze tickers and track your daily quota."}
      </p>
      <div className="auth-form">
        <input
          type="email"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && submit()}
          placeholder="you@example.com"
          autoComplete="email"
        />
        <input
          type="password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && submit()}
          placeholder="Password (min 8 characters)"
          autoComplete={mode === "login" ? "current-password" : "new-password"}
        />
        <button onClick={submit} disabled={busy} className="primary">
          {busy ? "Please wait…" : mode === "login" ? "Log in" : "Sign up"}
        </button>
      </div>
      {error && <div className="error-banner">{error}</div>}
      <p className="meta-text">
        {mode === "login" ? "No account yet? " : "Already have an account? "}
        <button
          className="link-button"
          onClick={() => {
            setMode(mode === "login" ? "signup" : "login");
            setError("");
          }}
        >
          {mode === "login" ? "Sign up" : "Log in"}
        </button>
      </p>
    </div>
  );
}

export default function App() {
  const [view, setView] = useState<View>("ingest");
  const [ticker, setTicker] = useState("");
  const [phase, setPhase] = useState<Phase>("idle");
  const [job, setJob] = useState<IngestJob | null>(null);
  const [stats, setStats] = useState<IngestStats | null>(null);
  const [error, setError] = useState("");
  const [history, setHistory] = useState<IngestedTicker[]>([]);

  const [numbers, setNumbers] = useState<NumbersResponse | null>(null);
  const [numbersTicker, setNumbersTicker] = useState("");
  const [numbersError, setNumbersError] = useState("");
  const [numbersLoading, setNumbersLoading] = useState(false);

  const [onePager, setOnePager] = useState<OnePagerResponse | null>(null);
  const [onePagerTicker, setOnePagerTicker] = useState("");
  const [onePagerError, setOnePagerError] = useState("");
  const [onePagerLoading, setOnePagerLoading] = useState(false);

  const [business, setBusiness] = useState<BusinessSwotResponse | null>(null);
  const [businessTicker, setBusinessTicker] = useState("");
  const [businessError, setBusinessError] = useState("");
  const [businessLoading, setBusinessLoading] = useState(false);

  const [financials, setFinancials] = useState<FinancialsResponse | null>(null);
  const [financialsTicker, setFinancialsTicker] = useState("");
  const [financialsError, setFinancialsError] = useState("");
  const [financialsLoading, setFinancialsLoading] = useState(false);

  const [strategy, setStrategy] = useState<StrategyResponse | null>(null);
  const [strategyTicker, setStrategyTicker] = useState("");
  const [strategyError, setStrategyError] = useState("");
  const [strategyLoading, setStrategyLoading] = useState(false);

  const [user, setUser] = useState<AuthUser | null>(null);
  const [quota, setQuota] = useState<QuotaStatus | null>(null);

  const loadQuota = useCallback(() => {
    getQuota()
      .then(setQuota)
      .catch(() => setQuota(null));
  }, []);

  useEffect(() => {
    if (!getToken()) return;
    getMe()
      .then((u) => {
        setUser(u);
        loadQuota();
      })
      .catch(() => setToken(null));
  }, [loadQuota]);

  async function handleAuthenticated(u: AuthUser) {
    setUser(u);
    loadQuota();
  }

  async function handleLogout() {
    try {
      await logout();
    } catch {
      // token is discarded client-side regardless
    }
    setToken(null);
    setUser(null);
    setQuota(null);
  }

  const refreshHistory = useCallback(() => {
    listIngested()
      .then(setHistory)
      .catch(() => setHistory([]));
  }, []);

  useEffect(() => {
    refreshHistory();
  }, [refreshHistory]);

  async function openStats(symbol: string) {
    const data = await getIngestStats(symbol);
    setStats(data);
    setPhase("done");
  }

  async function run(symbol: string) {
    const s = symbol.trim().toUpperCase();
    if (!s) return;
    setPhase("ingesting");
    setError("");
    setStats(null);
    setJob(null);
    try {
      const res = await ingestTicker(s);
      if (res.status === "cached") {
        await openStats(s);
        refreshHistory();
        loadQuota();
        return;
      }
      const jobId = res.job_id ?? "";
      while (true) {
        const current = await getIngestJob(jobId);
        setJob(current);
        if (current.status === "completed") {
          await openStats(s);
          refreshHistory();
          loadQuota();
          return;
        }
        if (current.status === "failed") {
          setError(current.error || "Ingestion failed");
          setPhase("error");
          return;
        }
        await new Promise((resolve) => setTimeout(resolve, 1000));
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : "Ingestion failed");
      setPhase("error");
    }
  }

  async function loadNumbers(symbol: string, force = false) {
    const s = symbol.trim().toUpperCase();
    if (!s) return;
    setNumbersTicker(s);
    setNumbersLoading(true);
    setNumbersError("");
    try {
      const data = force ? await refreshNumbers(s) : await getNumbers(s);
      setNumbers(data);
      if (force) loadQuota();
    } catch (e) {
      if (!force) {
        try {
          setNumbers(await refreshNumbers(s));
          loadQuota();
          return;
        } catch (e2) {
          setNumbersError(e2 instanceof Error ? e2.message : "Failed to load numbers");
        }
      } else {
        setNumbersError(e instanceof Error ? e.message : "Failed to load numbers");
      }
    } finally {
      setNumbersLoading(false);
    }
  }

  const byItemRows = stats ? Object.entries(stats.chunks_by_item).sort() : [];
  const byYearRows = stats ? Object.entries(stats.chunks_by_year).sort() : [];

  async function ensureNumbers(symbol: string) {
    try {
      await getNumbers(symbol);
    } catch {
      await refreshNumbers(symbol);
      loadQuota();
    }
  }

  async function loadOnePager(symbol: string) {
    const s = symbol.trim().toUpperCase();
    if (!s) return;
    setOnePagerTicker(s);
    setOnePagerLoading(true);
    setOnePagerError("");
    try {
      await ensureNumbers(s);
      setOnePager(await getOnePager(s));
    } catch (e) {
      setOnePagerError(e instanceof Error ? e.message : "Failed to load one-pager");
    } finally {
      setOnePagerLoading(false);
    }
  }

  async function setGate(decision: "accept" | "reject") {
    if (!onePagerTicker || !onePager) return;
    setOnePagerError("");
    try {
      const res = await setStepGate(onePagerTicker, decision);
      setOnePager({ ...onePager, gate: res.gate });
    } catch (e) {
      setOnePagerError(e instanceof Error ? e.message : "Failed to save decision");
    }
  }

  async function loadBusinessSwot(symbol: string) {
    const s = symbol.trim().toUpperCase();
    if (!s) return;
    setBusinessTicker(s);
    setBusinessLoading(true);
    setBusinessError("");
    try {
      setBusiness(await getBusinessSwot(s));
    } catch (e) {
      setBusinessError(e instanceof Error ? e.message : "Failed to load business & SWOT");
    } finally {
      setBusinessLoading(false);
    }
  }

  async function loadFinancials(symbol: string) {
    const s = symbol.trim().toUpperCase();
    if (!s) return;
    setFinancialsTicker(s);
    setFinancialsLoading(true);
    setFinancialsError("");
    try {
      await ensureNumbers(s);
      setFinancials(await getFinancials(s));
    } catch (e) {
      setFinancialsError(e instanceof Error ? e.message : "Failed to load financials");
    } finally {
      setFinancialsLoading(false);
    }
  }

  async function loadStrategy(symbol: string) {
    const s = symbol.trim().toUpperCase();
    if (!s) return;
    setStrategyTicker(s);
    setStrategyLoading(true);
    setStrategyError("");
    try {
      await ensureNumbers(s);
      setStrategy(await getStrategy(s));
    } catch (e) {
      setStrategyError(e instanceof Error ? e.message : "Failed to load strategy");
    } finally {
      setStrategyLoading(false);
    }
  }

  return (
    <div className="app">
      {!user ? (
        <AuthPanel onAuthenticated={handleAuthenticated} />
      ) : (
        <>
          <header className="header">
            <h1>Financial Analyst</h1>
            <div className="user-bar">
              <span className="meta-text">
                {user.email}
                {user.verified ? " · verified" : " · unverified"}
              </span>
              {quota && (
                <span className="meta-text">
                  analyses {quota.analyses.used}/{quota.analyses.limit} · chat{" "}
                  {quota.chat.used}/{quota.chat.limit}
                </span>
              )}
              <button onClick={handleLogout} className="link-button">
                Log out
              </button>
            </div>
            <nav className="tabs">
              <button className={view === "ingest" ? "tab active" : "tab"} onClick={() => setView("ingest")}>
                Ingest
              </button>
              {DOSSIER_STEPS.map((step) => (
                <button
                  key={step.n}
                  className={view === step.view ? "tab active" : "tab"}
                  onClick={() => setView(step.view)}
                >
                  Step {step.n}
                </button>
              ))}
              <button className={view === "numbers" ? "tab active" : "tab"} onClick={() => setView("numbers")}>
                Financials
              </button>
            </nav>
          </header>

          {view === "ingest" ? (
        <>
          <div className="search">
            <input
              value={ticker}
              onChange={(e) => setTicker(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && run(ticker)}
              placeholder="e.g. TSLA"
              className="ticker-input"
            />
            <button onClick={() => run(ticker)} disabled={phase === "ingesting"} className="primary">
              Ingest
            </button>
          </div>

          {phase === "ingesting" && (
            <div className="status">
              <span className="spinner" aria-hidden="true" />
              {job
                ? `Ingesting ${job.ticker} — ${job.status} (${job.progress}%)`
                : `Ingesting ${ticker.toUpperCase()} — starting job…`}
              <progress value={job?.progress ?? 0} max={100} style={{ display: "block", width: "100%", marginTop: 8 }} />
            </div>
          )}

          {phase === "error" && <div className="error-banner">{error}</div>}

          <div className="layout">
            <main className="content">
              {phase === "done" && stats && (
                <article>
                  <div className="report-meta">
                    <span className="meta-text">
                      {stats.ticker} · ingested {stats.ingested_at.slice(0, 10)} · {stats.num_chunks} chunks ·
                      fiscal years {stats.fiscal_years.join(", ")}
                    </span>
                  </div>
                  <ChunkTable title="Chunks by Item" rows={byItemRows} />
                  <ChunkTable title="Chunks by Fiscal Year" rows={byYearRows} />
                </article>
              )}
            </main>

            <aside className="sidebar">
              <h2>Ingested tickers</h2>
              {history.length === 0 && <p>Nothing ingested yet.</p>}
              <ul>
                {history.map((h) => (
                  <li key={h.ticker}>
                    <button onClick={() => openStats(h.ticker)} className="history-link">
                      {h.ticker}
                      {h.fiscal_years?.length ? ` (${h.fiscal_years.join("/")})` : ""}
                    </button>
                  </li>
                ))}
              </ul>
            </aside>
          </div>
        </>
      ) : view === "step1" ? (
        <div className="layout">
          <main className="content">
            <div className="search">
              <input
                value={onePagerTicker}
                onChange={(e) => setOnePagerTicker(e.target.value)}
                onKeyDown={(e) => e.key === "Enter" && loadOnePager(onePagerTicker)}
                placeholder="e.g. TSLA"
                className="ticker-input"
              />
              <button
                onClick={() => loadOnePager(onePagerTicker)}
                disabled={onePagerLoading}
                className="primary"
              >
                Load
              </button>
            </div>
            {onePagerLoading && <div className="status">Loading one-pager…</div>}
            {onePagerError && <div className="error-banner">{onePagerError}</div>}
            {onePager && <OnePagerCard response={onePager} onGate={setGate} />}
          </main>
        </div>
      ) : view === "step2" ? (
        <div className="layout">
          <main className="content">
            <div className="search">
              <input
                value={businessTicker}
                onChange={(e) => setBusinessTicker(e.target.value)}
                onKeyDown={(e) => e.key === "Enter" && loadBusinessSwot(businessTicker)}
                placeholder="e.g. TSLA"
                className="ticker-input"
              />
              <button
                onClick={() => loadBusinessSwot(businessTicker)}
                disabled={businessLoading}
                className="primary"
              >
                Load
              </button>
            </div>
            {businessLoading && <div className="status">Drafting Business & SWOT…</div>}
            {businessError && <div className="error-banner">{businessError}</div>}
            {business && <BusinessSwotCard response={business} />}
            {business && businessTicker && (
              <ChatPanel ticker={businessTicker} step={2} label="Business & SWOT" />
            )}
          </main>
        </div>
      ) : view === "step3" ? (
        <div className="layout">
          <main className="content">
            <div className="search">
              <input
                value={financialsTicker}
                onChange={(e) => setFinancialsTicker(e.target.value)}
                onKeyDown={(e) => e.key === "Enter" && loadFinancials(financialsTicker)}
                placeholder="e.g. TSLA"
                className="ticker-input"
              />
              <button
                onClick={() => loadFinancials(financialsTicker)}
                disabled={financialsLoading}
                className="primary"
              >
                Load
              </button>
            </div>
            {financialsLoading && <div className="status">Drafting Financials…</div>}
            {financialsError && <div className="error-banner">{financialsError}</div>}
            {financials && <FinancialsCard response={financials} />}
            {financials && financialsTicker && (
              <PeerScorecardPanel ticker={financialsTicker} onQuotaChange={loadQuota} />
            )}
            {financials && financialsTicker && (
              <ChatPanel ticker={financialsTicker} step={3} label="Financials" />
            )}
          </main>
        </div>
      ) : view === "step4" ? (
        <div className="layout">
          <main className="content">
            <div className="search">
              <input
                value={strategyTicker}
                onChange={(e) => setStrategyTicker(e.target.value)}
                onKeyDown={(e) => e.key === "Enter" && loadStrategy(strategyTicker)}
                placeholder="e.g. TSLA"
                className="ticker-input"
              />
              <button
                onClick={() => loadStrategy(strategyTicker)}
                disabled={strategyLoading}
                className="primary"
              >
                Load
              </button>
            </div>
            {strategyLoading && <div className="status">Drafting Strategy…</div>}
            {strategyError && <div className="error-banner">{strategyError}</div>}
            {strategy && <StrategyCard response={strategy} />}
            {strategy && strategyTicker && (
              <ChatPanel ticker={strategyTicker} step={4} label="Strategy" />
            )}
          </main>
        </div>
      ) : view === "numbers" ? (
        <div className="layout">
          <main className="content">
            <div className="search">
              <input
                value={numbersTicker}
                onChange={(e) => setNumbersTicker(e.target.value)}
                onKeyDown={(e) => e.key === "Enter" && loadNumbers(numbersTicker, false)}
                placeholder="e.g. TSLA"
                className="ticker-input"
              />
              <button onClick={() => loadNumbers(numbersTicker, false)} disabled={numbersLoading} className="primary">
                Load
              </button>
              <button onClick={() => loadNumbers(numbersTicker, true)} disabled={numbersLoading} className="primary">
                Refresh
              </button>
            </div>
            {numbersLoading && <div className="status">Loading numbers…</div>}
            {numbersError && <div className="error-banner">{numbersError}</div>}
            {numbers && (
              <article>
                <div className="report-meta">
                  <span className="meta-text">
                    {numbers.ticker} · refreshed {numbers.refreshed_at.slice(0, 10)} · fiscal years{" "}
                    {numbers.financials.fiscal_years.join(", ")}
                  </span>
                </div>
                <PriceCard ticker={numbers.ticker} numbers={numbers} onSaved={setNumbers} />
                <MatrixTable
                  title="Income Statement"
                  matrix={numbers.financials.income_statement}
                  years={numbers.financials.fiscal_years.map(String)}
                />
                <MatrixTable
                  title="Balance Sheet"
                  matrix={numbers.financials.balance_sheet}
                  years={numbers.financials.fiscal_years.map(String)}
                />
                <MatrixTable
                  title="Cash Flow"
                  matrix={numbers.financials.cash_flow}
                  years={numbers.financials.fiscal_years.map(String)}
                />
                <MatrixTable
                  title="Common-Size Income (% of revenue)"
                  matrix={numbers.financials.common_size.income_statement}
                  years={numbers.financials.fiscal_years.map(String)}
                  format={formatPercent}
                />
                <MatrixTable
                  title="Common-Size Balance (% of assets)"
                  matrix={numbers.financials.common_size.balance_sheet}
                  years={numbers.financials.fiscal_years.map(String)}
                  format={formatPercent}
                />
                <MatrixTable
                  title="Ratios"
                  matrix={numbers.financials.ratios}
                  format={formatPercent}
                />
                <MatrixTable
                  title="CAGR (revenue & profit)"
                  matrix={numbers.financials.cagr}
                  years={["5", "10", "15"]}
                  yearLabel={(span) => `${span}y`}
                  format={formatPercent}
                />
              </article>
            )}
          </main>
        </div>
      ) : (
        <div className="layout">
          <main className="content">
            <div className="report-meta">
              <span className="meta-text">
                {(() => {
                  const step = DOSSIER_STEPS.find((s) => s.view === view);
                  return `Step ${step?.n} · ${step?.label}`;
                })()}
              </span>
            </div>
            <p className="meta-text">This step is not built yet.</p>
          </main>
        </div>
      )}
        </>
      )}
    </div>
  );
}
