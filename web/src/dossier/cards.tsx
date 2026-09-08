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
      <span className="meta-text">{label}</span>
      <span>{value}</span>
    </div>
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

export function BusinessSwotCard({ response }: { response: BusinessSwotResponse }) {
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

export function FinancialsCard({ response }: { response: FinancialsResponse }) {
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

export function StrategyCard({ response }: { response: StrategyResponse }) {
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
