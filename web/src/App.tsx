import { useCallback, useEffect, useState } from "react";
import {
  clearPriceOverride,
  getEvalSummary,
  getIngestJob,
  getMe,
  getNumbers,
  getPortfolio,
  getQuota,
  getToken,
  ingestTicker,
  login,
  logout,
  refreshNumbers,
  setPriceOverride,
  setToken,
  signup,
} from "./api";
import type {
  AuthUser,
  EvalSummary,
  IngestJob,
  NumbersResponse,
  PortfolioRow,
  QuotaStatus,
} from "./api";
import { formatMoney, formatPercent } from "./dossier/format";
import { useDossier } from "./dossier/useDossier";
import { useLibrary } from "./dossier/useLibrary";
import { CompanyWorkspace } from "./dossier/companyWorkspace";
import { NoCompanyPrompt } from "./dossier/noCompany";
import { PortfolioView } from "./dossier/portfolioView";
import { LibraryView } from "./dossier/libraryView";
import {
  BrandMark,
  LogOutIcon,
  SearchIcon,
} from "./dossier/icons";

type Phase = "idle" | "ingesting" | "error";
type Section = "portfolio" | "dossier" | "numbers" | "eval" | "library";

const EVAL_STEP_LABELS: Record<string, string> = {
  "2": "Step 2 · Business & SWOT",
  "3": "Step 3 · Financials",
  "4": "Step 4 · Strategy",
  search_all: "Search everything",
};

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
      <div className="matrix-scroll">
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
      </div>
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

  if (!price) {
    return (
      <div className="price-card">
        <h2>Price</h2>
        <p className="meta-text">No price available yet.</p>
      </div>
    );
  }

  return (
    <div className="price-card">
      <div className="price-top">
        <h2>Price</h2>
        <span className="price-value">${price.effective.price.toFixed(2)}</span>
        <span className="meta-text">
          {price.effective.source === "override" ? "manual override" : "yahoo finance"}
        </span>
        {price.override && (
          <span className="meta-text">
            Override ${price.override.price.toFixed(2)} set {price.override.set_at.slice(0, 10)}.
          </span>
        )}
      </div>
      <div className="override-row">
        <input
          type="number"
          step="0.01"
          min="0"
          value={override}
          onChange={(e) => setOverride(e.target.value)}
          placeholder="Manual price override"
          className="text-input"
        />
        <button onClick={saveOverride} disabled={saving} className="btn btn-secondary btn-sm">
          Override
        </button>
        {price.override && (
          <button
            onClick={removeOverride}
            disabled={saving}
            className="link-button"
          >
            Remove override
          </button>
        )}
      </div>
      {error && <div className="error-banner">{error}</div>}
      {price.history.length > 0 && (
        <p className="meta-text">Price history: {price.history.length} daily points.</p>
      )}
    </div>
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
    <div className="auth-shell">
      <div className="auth-card card">
        <div className="auth-inner">
          <a className="auth-brand" href="/" onClick={(e) => e.preventDefault()}>
            <span className="brand-mark">
              <BrandMark />
            </span>
            <span className="brand-name">Financial Analyst</span>
          </a>
          <h1 className="auth-title">{mode === "login" ? "Log in" : "Create an account"}</h1>
          <p className="auth-sub">
            {mode === "signup"
              ? "Accounts work immediately. Unverified accounts get stricter daily quotas."
              : "Log in to analyze tickers and track your daily quota."}
          </p>
          <form
            className="auth-form"
            onSubmit={(e) => {
              e.preventDefault();
              submit();
            }}
          >
            <input
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="you@example.com"
              autoComplete="email"
              className="text-input"
              aria-label="Email"
            />
            <input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder={mode === "signup" ? "Password (min 8 characters)" : "Password"}
              autoComplete={mode === "login" ? "current-password" : "new-password"}
              className="text-input"
              aria-label="Password"
            />
            <button type="submit" disabled={busy} className="btn btn-primary">
              {busy ? "Please wait…" : mode === "login" ? "Log in" : "Sign up"}
            </button>
          </form>
          {error && (
            <div className="error-banner" style={{ marginTop: 14 }}>
              {error}
            </div>
          )}
          <div className="auth-foot">
            <span className="meta-text">
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
            </span>
          </div>
        </div>
      </div>
    </div>
  );
}

function QuotaMeter({ quota }: { quota: QuotaStatus }) {
  const analysesPct = Math.min(100, (quota.analyses.used / Math.max(quota.analyses.limit, 1)) * 100);
  const chatPct = Math.min(100, (quota.chat.used / Math.max(quota.chat.limit, 1)) * 100);
  const meterVar = (pct: number) => ({ ["--meter-p" as string]: `${pct / 100}` });
  return (
    <div className="quota" title="Daily quotas reset at midnight (UTC)">
      <div className="quota-item">
        <div className="quota-top">
          <span className="quota-label">Analyses</span>
          <span className="quota-value">
            {quota.analyses.used}/{quota.analyses.limit}
          </span>
        </div>
        <div className="meter">
          <div
            className={`meter-fill${analysesPct >= 100 ? " exhausted" : ""}`}
            style={meterVar(analysesPct)}
          />
        </div>
      </div>
      <div className="quota-item">
        <div className="quota-top">
          <span className="quota-label">Chat</span>
          <span className="quota-value">
            {quota.chat.used}/{quota.chat.limit}
          </span>
        </div>
        <div className="meter">
          <div
            className={`meter-fill${chatPct >= 100 ? " exhausted" : ""}`}
            style={meterVar(chatPct)}
          />
        </div>
      </div>
    </div>
  );
}

export default function App() {
  const [section, setSection] = useState<Section>("portfolio");
  const [company, setCompany] = useState<string | null>(null);
  const [activeStep, setActiveStep] = useState(1);
  const [phase, setPhase] = useState<Phase>("idle");
  const [tickerInput, setTickerInput] = useState("");
  const [job, setJob] = useState<IngestJob | null>(null);
  const [error, setError] = useState("");

  const [portfolioRows, setPortfolioRows] = useState<PortfolioRow[]>([]);
  const [portfolioLoading, setPortfolioLoading] = useState(false);
  const [portfolioError, setPortfolioError] = useState("");

  const [numbers, setNumbers] = useState<NumbersResponse | null>(null);
  const [numbersTicker, setNumbersTicker] = useState("");
  const [numbersError, setNumbersError] = useState("");
  const [numbersLoading, setNumbersLoading] = useState(false);

  const [user, setUser] = useState<AuthUser | null>(null);
  const [quota, setQuota] = useState<QuotaStatus | null>(null);

  const [evalSummary, setEvalSummary] = useState<EvalSummary | null>(null);
  const [evalError, setEvalError] = useState("");
  const [evalLoading, setEvalLoading] = useState(false);

  const loadQuota = useCallback(() => {
    getQuota()
      .then(setQuota)
      .catch(() => setQuota(null));
  }, []);

  const dossier = useDossier(loadQuota);
  const library = useLibrary();
  const [workspaceReturn, setWorkspaceReturn] = useState<Section>("portfolio");

  useEffect(() => {
    if (!getToken()) return;
    getMe()
      .then((u) => {
        setUser(u);
        loadQuota();
      })
      .catch(() => setToken(null));
  }, [loadQuota]);

  useEffect(() => {
    if (section === "dossier" && company) {
      dossier.loadProgress(company);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [section, company]);

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
    setCompany(null);
    setPortfolioRows([]);
    setPortfolioError("");
    library.reset();
    setSection("portfolio");
  }

  const refreshPortfolio = useCallback(() => {
    if (!getToken()) return;
    setPortfolioLoading(true);
    setPortfolioError("");
    getPortfolio()
      .then(setPortfolioRows)
      .catch((e) => {
        setPortfolioRows([]);
        setPortfolioError(e instanceof Error ? e.message : "Failed to load portfolio");
      })
      .finally(() => setPortfolioLoading(false));
  }, []);

  useEffect(() => {
    if (section === "portfolio" && user) refreshPortfolio();
  }, [section, user, refreshPortfolio]);

  useEffect(() => {
    if (user) library.load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [user]);

  useEffect(() => {
    if (section === "library" && user) library.load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [section]);

  function openDossier(symbol: string, step: number, returnTo: "portfolio" | "library") {
    dossier.reset();
    setCompany(symbol);
    setActiveStep(step);
    setWorkspaceReturn(returnTo);
    setSection("dossier");
  }

  function openCompany(symbol: string) {
    openDossier(symbol, 1, "portfolio");
  }

  function openLibraryTicker(ticker: string) {
    openDossier(ticker, 6, "library");
  }

  async function finishIngest(symbol: string) {
    setPhase("idle");
    openCompany(symbol);
    refreshPortfolio();
    loadQuota();
  }

  async function run(symbol: string) {
    const s = symbol.trim().toUpperCase();
    if (!s) return;
    setPhase("ingesting");
    setError("");
    setJob(null);
    try {
      const res = await ingestTicker(s);
      if (res.status === "cached") {
        await finishIngest(s);
        return;
      }
      const jobId = res.job_id ?? "";
      while (true) {
        const current = await getIngestJob(jobId);
        setJob(current);
        if (current.status === "completed") {
          await finishIngest(s);
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

  function openNumbers(preferredTicker?: string) {
    const s = (preferredTicker ?? company ?? "").trim().toUpperCase();
    if (s) void loadNumbers(s);
    setSection("numbers");
  }

  async function loadEval() {
    if (evalLoading) return;
    setEvalLoading(true);
    setEvalError("");
    try {
      setEvalSummary(await getEvalSummary());
    } catch (e) {
      setEvalSummary(null);
      setEvalError(e instanceof Error ? e.message : "Failed to load eval results");
    } finally {
      setEvalLoading(false);
    }
  }

  const activeSection = (s: Section) => (section === s ? "navtab active" : "navtab");

  return (
    <div className="app">
      {!user ? (
        <AuthPanel onAuthenticated={handleAuthenticated} />
      ) : (
        <>
          <header className="topbar">
            <div className="topbar-inner">
              <a className="brand" href="/" onClick={(e) => e.preventDefault()}>
                <span className="brand-mark">
                  <BrandMark />
                </span>
                <span className="brand-name">Financial Analyst</span>
              </a>
              <nav className="mainnav" aria-label="Sections">
                <button
                  className={activeSection("portfolio")}
                  onClick={() => setSection("portfolio")}
                >
                  Portfolio
                </button>
                <button className={activeSection("library")} onClick={() => setSection("library")}>
                  Library
                </button>
                {company && (
                  <button
                    className={activeSection("dossier")}
                    onClick={() => setSection("dossier")}
                  >
                    Dossier
                  </button>
                )}
                <button className={activeSection("numbers")} onClick={() => openNumbers()}>
                  Numbers
                </button>
              </nav>
              <div className="topbar-spacer" />
              {quota && <QuotaMeter quota={quota} />}
              <div className="account">
                <span className="account-email" title={user.email}>
                  {user.email}
                </span>
                <span
                  className={`tier-dot ${user.verified ? "verified" : "unverified"}`}
                  title={user.verified ? "Verified account" : "Unverified account"}
                />
                <button
                  className="dev-link"
                  title="Retrieval-quality measurements"
                  onClick={() => {
                    setSection("eval");
                    loadEval();
                  }}
                >
                  Eval
                </button>
                <button onClick={handleLogout} className="logout-btn">
                  <LogOutIcon />
                  <span>Log out</span>
                </button>
              </div>
            </div>
          </header>

          {section === "portfolio" ? (
            <main className="page">
              <div className="page-head">
                <div>
                  <h1>Portfolio</h1>
                  <p className="page-sub">
                    Every ticker you have ingested, with its dossier progress and
                    gate status. Open one to continue its analysis.
                  </p>
                </div>
              </div>
              <div className="ingest-bar" role="search">
                <div className="ingest-field">
                  <SearchIcon />
                  <input
                    value={tickerInput}
                    onChange={(e) => setTickerInput(e.target.value)}
                    onKeyDown={(e) => e.key === "Enter" && run(tickerInput)}
                    placeholder="e.g. TSLA"
                    className="text-input"
                    aria-label="Ticker to ingest"
                  />
                </div>
                <button
                  onClick={() => run(tickerInput)}
                  disabled={phase === "ingesting"}
                  className="btn btn-primary"
                >
                  {phase === "ingesting" ? "Ingesting…" : "Ingest"}
                </button>
              </div>

              {phase === "ingesting" && (
                <div className="status">
                  <span className="spinner" aria-hidden="true" />
                  <span>
                    {job
                      ? `Ingesting ${job.ticker} — ${job.status} (${job.progress}%)`
                      : `Ingesting ${tickerInput.toUpperCase()} — starting job…`}
                  </span>
                </div>
              )}

              {phase === "ingesting" && job && (
                <progress
                  className="ingest-progress"
                  value={job.progress}
                  max={100}
                  aria-hidden="true"
                />
              )}

              {phase === "error" && <div className="error-banner">{error}</div>}

              <PortfolioView
                rows={portfolioRows}
                loading={portfolioLoading}
                error={portfolioError}
                onOpenCompany={openCompany}
              />
            </main>
          ) : section === "library" ? (
            <main className="page">
              <div className="page-head">
                <div>
                  <h1>Library</h1>
                  <p className="page-sub">
                    Tickers whose Step 6 thesis you saved. Open one to view its
                    read-only, source-tagged thesis.
                  </p>
                </div>
              </div>
              {library.actionError && <div className="error-banner">{library.actionError}</div>}
              <LibraryView
                rows={library.rows}
                loading={library.loading}
                error={library.error}
                onOpen={openLibraryTicker}
                onUnsave={(ticker) => {
                  library.unsave(ticker).then(() => refreshPortfolio());
                }}
              />
            </main>
          ) : section === "dossier" ? (
            company ? (
              <CompanyWorkspace
                ticker={company}
                activeStep={activeStep}
                onSelectStep={setActiveStep}
                onBack={() => setSection(workspaceReturn)}
                backLabel={workspaceReturn === "library" ? "Library" : "Portfolio"}
                onOpenNumbers={() => openNumbers(company)}
                onQuotaChange={loadQuota}
                dossier={dossier}
                saved={library.isSaved(company)}
                saveBusy={library.saving}
                saveError={library.actionError}
                onSaveToLibrary={() => {
                  library.save(company).then(() => refreshPortfolio());
                }}
                onUnsaveFromLibrary={() => {
                  library.unsave(company).then(() => refreshPortfolio());
                }}
              />
            ) : (
              <main className="page">
                <NoCompanyPrompt onOpenIngest={() => setSection("portfolio")} />
              </main>
            )
          ) : section === "numbers" ? (
            <main className="page">
              <div className="page-head">
                <div>
                  <h1>Numbers view</h1>
                  <p className="page-sub">
                    Raw statements and price — its own section, separate from the
                    dossier steps and free of the gate.
                  </p>
                </div>
              </div>
              <div className="search numbers-toolbar">
                <div className="ingest-field">
                  <SearchIcon />
                  <input
                    value={numbersTicker}
                    onChange={(e) => setNumbersTicker(e.target.value)}
                    onKeyDown={(e) => e.key === "Enter" && loadNumbers(numbersTicker, false)}
                    placeholder="e.g. TSLA"
                    className="text-input"
                    aria-label="Ticker to load"
                  />
                </div>
                <button
                  onClick={() => loadNumbers(numbersTicker, false)}
                  disabled={numbersLoading}
                  className="btn btn-primary btn-sm"
                >
                  Load
                </button>
                <button
                  onClick={() => loadNumbers(numbersTicker, true)}
                  disabled={numbersLoading}
                  className="btn btn-secondary btn-sm"
                >
                  Refresh from EDGAR
                </button>
              </div>
              {numbersLoading && (
                <div className="status">
                  <span className="spinner" aria-hidden="true" />
                  <span>Loading numbers…</span>
                </div>
              )}
              {numbersError && <div className="error-banner">{numbersError}</div>}
              {numbers && (
                <div className="card">
                  <div className="doc-body">
                    <div className="numbers-meta">
                      <div className="numbers-headline">
                        <span className="ticker">{numbers.ticker}</span>
                        <span className="meta-text">
                          refreshed {numbers.refreshed_at.slice(0, 10)} · fiscal years{" "}
                          {numbers.financials.fiscal_years.join(", ")}
                        </span>
                      </div>
                    </div>
                    <PriceCard ticker={numbers.ticker} numbers={numbers} onSaved={setNumbers} />
                    <MatrixTable
                      title="Income statement"
                      matrix={numbers.financials.income_statement}
                      years={numbers.financials.fiscal_years.map(String)}
                    />
                    <MatrixTable
                      title="Balance sheet"
                      matrix={numbers.financials.balance_sheet}
                      years={numbers.financials.fiscal_years.map(String)}
                    />
                    <MatrixTable
                      title="Cash flow"
                      matrix={numbers.financials.cash_flow}
                      years={numbers.financials.fiscal_years.map(String)}
                    />
                    <MatrixTable
                      title="Common-size income (% of revenue)"
                      matrix={numbers.financials.common_size.income_statement}
                      years={numbers.financials.fiscal_years.map(String)}
                      format={formatPercent}
                    />
                    <MatrixTable
                      title="Common-size balance (% of assets)"
                      matrix={numbers.financials.common_size.balance_sheet}
                      years={numbers.financials.fiscal_years.map(String)}
                      format={formatPercent}
                    />
                    <MatrixTable title="Ratios" matrix={numbers.financials.ratios} format={formatPercent} />
                    <MatrixTable
                      title="CAGR (revenue & profit)"
                      matrix={numbers.financials.cagr}
                      years={["5", "10", "15"]}
                      yearLabel={(span) => `${span}y`}
                      format={formatPercent}
                    />
                  </div>
                </div>
              )}
            </main>
          ) : (
            <main className="page">
              <div className="page-head">
                <div>
                  <h1>Eval</h1>
                  <p className="page-sub">
                    Retrieval-quality measurements per configuration — the
                    evidence behind this product. A quiet corner, not a part of
                    the investor workflow.
                  </p>
                </div>
                <div className="search">
                  <button onClick={loadEval} disabled={evalLoading} className="btn btn-secondary btn-sm">
                    Refresh
                  </button>
                </div>
              </div>
              {evalLoading && (
                <div className="status">
                  <span className="spinner" aria-hidden="true" />
                  <span>Loading eval results…</span>
                </div>
              )}
              {evalError && <div className="error-banner">{evalError}</div>}
              {!evalLoading && !evalError && evalSummary && (
                <div className="card">
                  <div className="doc-body">
                    <EvalPanel summary={evalSummary} />
                  </div>
                </div>
              )}
              {!evalLoading && !evalError && !evalSummary && (
                <div className="status">
                  No eval results yet — run the eval CLI (python -m
                  financial_analyst.evaluation.cli curated | regression | smoke).
                </div>
              )}
            </main>
          )}
        </>
      )}
    </div>
  );
}

function EvalPanel({ summary }: { summary: EvalSummary }) {
  const hasAny =
    summary.curated.length > 0 ||
    summary.regression.length > 0 ||
    summary.smoke.length > 0;
  if (!hasAny) {
    return (
      <div className="status">
        No eval results yet — run the eval CLI (python -m financial_analyst.evaluation.cli
        curated | regression | smoke).
      </div>
    );
  }

  const fmt = (v: number | null | undefined) =>
    v === null || v === undefined ? "n/a" : v.toFixed(3);
  const fmtDelta = (v: number | null | undefined) =>
    v === null || v === undefined ? "n/a" : `${v >= 0 ? "+" : ""}${v.toFixed(3)}`;
  const when = (iso: string) => (iso ? new Date(iso).toLocaleString() : "");

  return (
    <div className="report-view">
      {summary.curated.length > 0 && (
        <section className="eval-block">
          <h2>Curated Tesla benchmark · per-step retrieval</h2>
          {summary.curated.map((entry) => (
            <div key={`${entry.name}-${entry.config}-${entry.run_at}`} className="eval-run">
              <div className="report-meta">
                <span>
                  {entry.name} · {entry.ticker} · {entry.config} · top_k {entry.top_k} ·{" "}
                  {when(entry.run_at)}
                </span>
              </div>
              <div className="matrix-scroll">
                <table className="matrix">
                  <thead>
                    <tr>
                      <th className="row-label">Dossier step</th>
                      <th>Queries</th>
                      <th>MRR</th>
                      <th>Hit rate</th>
                      <th>NDCG</th>
                    </tr>
                  </thead>
                  <tbody>
                    {Object.entries(entry.per_step).map(([step, m]) => (
                      <tr key={step}>
                        <td className="row-label">{EVAL_STEP_LABELS[step] ?? step}</td>
                        <td>{m.num_queries}</td>
                        <td>{fmt(m.mrr)}</td>
                        <td>{fmt(m.hit_rate)}</td>
                        <td>{fmt(m.ndcg)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          ))}
        </section>
      )}

      {summary.regression.length > 0 && (
        <section className="eval-block">
          <h2>Synthetic regression sets · continuity vs baseline</h2>
          <div className="matrix-scroll">
            <table className="matrix">
              <thead>
                <tr>
                  <th className="row-label">Dataset</th>
                  <th>Config</th>
                  <th>Queries</th>
                  <th>MRR</th>
                  <th>Hit rate</th>
                  <th>NDCG</th>
                  <th>Baseline MRR</th>
                  <th>Δ MRR</th>
                  <th>Status</th>
                </tr>
              </thead>
              <tbody>
                {summary.regression.map((r) => (
                  <tr key={`${r.dataset}-${r.config}`}>
                    <td className="row-label">{r.dataset}</td>
                    <td>{r.config}</td>
                    <td>{r.num_queries}</td>
                    <td>{fmt(r.mrr)}</td>
                    <td>{fmt(r.hit_rate)}</td>
                    <td>{fmt(r.ndcg)}</td>
                    <td>{fmt(r.baseline_mrr)}</td>
                    <td>{fmtDelta(r.delta_mrr)}</td>
                    <td>
                      <span className={r.regressed ? "badge badge-fail" : "badge badge-pass"}>
                        {r.regressed
                          ? `REGRESSION${r.regressions.length ? `: ${r.regressions.join(", ")}` : ""}`
                          : "OK"}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      )}

      {summary.smoke.length > 0 && (
        <section className="eval-block">
          <h2>Per-company smoke evals</h2>
          {summary.smoke.map((s) => (
            <div key={`${s.ticker}-${s.run_at}`} className="eval-run">
              <div className="report-meta">
                <span>{s.ticker} · {when(s.run_at)} · </span>
                <span className={s.passed ? "badge badge-pass" : "badge badge-fail"}>
                  {s.passed ? "PASS" : "FAIL"}
                </span>
              </div>
              <div className="matrix-scroll">
                <table className="matrix">
                  <thead>
                    <tr>
                      <th className="row-label">Step</th>
                      <th>Samples</th>
                      <th>Self-hit rate</th>
                      <th>In-scope rate</th>
                      <th>Missing scope items</th>
                    </tr>
                  </thead>
                  <tbody>
                    {Object.entries(s.steps).map(([step, r]) => (
                      <tr key={step}>
                        <td className="row-label">{EVAL_STEP_LABELS[step] ?? step}</td>
                        <td>{r.skipped ? "skipped" : r.samples}</td>
                        <td>{r.skipped ? "n/a" : fmt(r.retrieval_hit_rate)}</td>
                        <td>{r.skipped ? "n/a" : fmt(r.in_scope_rate)}</td>
                        <td>{s.checks[step]?.items_missing.join(", ") || "none"}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          ))}
        </section>
      )}
    </div>
  );
}
