import { useCallback, useEffect, useState } from "react";
import {
  clearPriceOverride,
  getIngestJob,
  getIngestStats,
  getMe,
  getNumbers,
  getQuota,
  getToken,
  ingestTicker,
  listIngested,
  login,
  logout,
  refreshNumbers,
  setPriceOverride,
  setToken,
  signup,
  AuthUser,
  IngestJob,
  IngestedTicker,
  IngestStats,
  NumbersResponse,
  QuotaStatus,
} from "./api";

type Phase = "idle" | "ingesting" | "done" | "error";
type View = "ingest" | "numbers";

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
      ) : (
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
      )}
        </>
      )}
    </div>
  );
}
