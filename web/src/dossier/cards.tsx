import type {
  BusinessSwotResponse,
  FinancialsResponse,
  OnePagerResponse,
  StrategyResponse,
} from "../api";
import { formatMoney } from "./format";
import { ArtifactSectionCard, FinancialsTableCard } from "./artifacts";

export function MetricRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="metric-row">
      <span>{label}</span>
      <span className="value">{value}</span>
    </div>
  );
}

export function VerdictChip({
  label,
  score,
}: {
  label: string;
  score: number;
}) {
  return (
    <span className="verdict-chip">
      <span className="verdict-score">{score}</span>
      <span className="verdict-label">{label}</span>
    </span>
  );
}

export function OnePagerCard({
  response,
  onGate,
}: {
  response: OnePagerResponse;
  onGate: (decision: "accept" | "reject") => void;
}) {
  const { one_pager: op, gate } = response;
  const pct = (v: number | null) => (v === null ? "n/a" : `${(v * 100).toFixed(1)}%`);
  const verdict = op.tag.label;
  return (
    <div className="report-view">
      <div className="report-meta">
        <span>
          One-pager · {response.ticker}
          {op.latest_fiscal_year ? ` · FY${op.latest_fiscal_year}` : ""} ·{" "}
          {op.source}
        </span>
      </div>
      <div className="verdict-row">
        <VerdictChip label={verdict} score={op.tag.score} />
        <span className="verdict-meta">{op.tag.rationale}</span>
      </div>
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

      <div className="gate-block">
        <span className="panel-title">The gate</span>
        {gate === null ? (
          <>
            <p className="gate-copy">
              Nothing past this step opens until you accept the deep dive. A
              Reject closes the dossier; you can reopen and accept it later.
            </p>
            <div className="gate-actions">
              <button onClick={() => onGate("accept")} className="btn btn-primary">
                Accept — deep dive
              </button>
              <button onClick={() => onGate("reject")} className="btn btn-danger">
                Reject
              </button>
            </div>
          </>
        ) : gate.status === "accepted" ? (
          <div className="gate-verdict">
            <div className="gate-verdict-line">
              <span className="status-chip status-accepted">Accepted</span>
              <span className="verdict-meta">
                on {gate.updated_at.slice(0, 10)} — deep dive approved.
              </span>
            </div>
            <button className="link-button" onClick={() => onGate("reject")}>
              Reject instead
            </button>
          </div>
        ) : (
          <div className="gate-verdict">
            <div className="gate-verdict-line">
              <span className="status-chip status-rejected">Rejected</span>
              <span className="verdict-meta">
                on {gate.updated_at.slice(0, 10)} — flow stopped. Rejection is
                not a write-off: you can reopen and accept later.
              </span>
            </div>
            <button className="link-button" onClick={() => onGate("accept")}>
              Accept instead
            </button>
          </div>
        )}
      </div>
    </div>
  );
}

export function BusinessSwotCard({ response }: { response: BusinessSwotResponse }) {
  const { artifact, cached } = response;
  const factSections = artifact.sections.filter((s) => !s.key.startsWith("swot_"));
  const swotSections = artifact.sections.filter((s) => s.key.startsWith("swot_"));
  return (
    <div className="report-view">
      <div className="report-meta">
        <span>
          Business &amp; SWOT · {artifact.ticker}
          {artifact.fiscal_year ? ` · FY${artifact.fiscal_year}` : ""}
        </span>
        <span className="source-tag">
          {cached ? "cached draft" : "freshly drafted"}
        </span>
      </div>
      {factSections.map((section) => (
        <ArtifactSectionCard key={section.key} section={section} />
      ))}
      <h2 className="swot-heading">SWOT</h2>
      <div className="swot-grid">
        {swotSections.map((section) => (
          <div key={section.key} className={`swot-cell swot-${section.key.replace("swot_", "")}`}>
            <ArtifactSectionCard section={section} />
          </div>
        ))}
      </div>
    </div>
  );
}

export function FinancialsCard({ response }: { response: FinancialsResponse }) {
  const { artifact, cached } = response;
  return (
    <div className="report-view">
      <div className="report-meta">
        <span>
          Financials · {artifact.ticker}
          {artifact.fiscal_year ? ` · FY${artifact.fiscal_year}` : ""}
        </span>
        <span className="source-tag">
          {cached ? "cached draft" : "freshly drafted"}
        </span>
      </div>
      {artifact.tables.map((table) => (
        <FinancialsTableCard key={table.key} table={table} />
      ))}
      <h2 className="swot-heading">Forensic note</h2>
      {artifact.sections.map((section) => (
        <ArtifactSectionCard key={section.key} section={section} />
      ))}
    </div>
  );
}

export function StrategyCard({ response }: { response: StrategyResponse }) {
  const { artifact, cached } = response;
  return (
    <div className="report-view">
      <div className="report-meta">
        <span>
          Strategy · {artifact.ticker}
          {artifact.fiscal_year ? ` · FY${artifact.fiscal_year}` : ""}
        </span>
        <span className="source-tag">
          {cached ? "cached draft" : "freshly drafted"}
        </span>
      </div>
      {artifact.returns && <FinancialsTableCard table={artifact.returns} />}
      {artifact.sections.map((section) => (
        <ArtifactSectionCard key={section.key} section={section} />
      ))}
    </div>
  );
}
