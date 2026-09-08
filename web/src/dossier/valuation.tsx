import type { ValuationResponse } from "../api";
import { formatMoney, formatPercent } from "./format";

export const VALUATION_STEP_LABELS: Record<number, string> = {
  1: "Step 1 · One-pager",
  2: "Step 2 · Business & SWOT",
  3: "Step 3 · Financials",
  4: "Step 4 · Strategy",
};

function fmtMoney(value: number | null | undefined) {
  return value === null || value === undefined ? "—" : formatMoney(value);
}

function fmtMultiple(value: number | null | undefined) {
  return value === null || value === undefined ? "—" : value.toFixed(2);
}

function fmtPct(value: number | null | undefined) {
  return value === null || value === undefined ? "—" : formatPercent(value);
}

export function ValuationPanel({
  response,
  discountPct,
  growthPct,
  onDiscountChange,
  onGrowthChange,
  onToggleDone,
  onApplyAssumptions,
}: {
  response: ValuationResponse;
  discountPct: string;
  growthPct: string;
  onDiscountChange: (value: string) => void;
  onGrowthChange: (value: string) => void;
  onToggleDone: (step: number, done: boolean) => void;
  onApplyAssumptions: () => void;
}) {
  const valuation = response.valuation ?? null;
  const dcf = valuation?.dcf ?? null;

  return (
    <section>
      <div className="report-meta">
        <span className="meta-text">
          Valuation is locked until you mark steps 1-4 done, so the price
          cannot bias your earlier analysis.
        </span>
      </div>

      <div className="peer-list">
        {Object.entries(VALUATION_STEP_LABELS).map(([step, label]) => {
          const done = response.done[step] ?? false;
          return (
            <span key={step} className="peer-chip">
              {label}
              <button
                onClick={() => onToggleDone(Number(step), done)}
                className="link-button"
                aria-label={`${done ? "Unmark" : "Mark"} ${label} done`}
              >
                {done ? "Done — undo" : "mark done"}
              </button>
            </span>
          );
        })}
      </div>

      {!valuation ? (
        <div className="status">
          Valuation locked. Finish reviewing the steps above to unlock it.
        </div>
      ) : (
        <>
          {dcf && (
            <section className="matrix-block">
              <h2>DCF · single-stage growing perpetuity</h2>
              <div className="price-card">
                <label>
                  Discount rate (%):
                  <input
                    value={discountPct}
                    onChange={(e) => onDiscountChange(e.target.value)}
                    className="ticker-input"
                    style={{ width: 80, marginLeft: 8 }}
                  />
                </label>
                <label style={{ marginLeft: 12 }}>
                  Growth (%):
                  <input
                    value={growthPct}
                    onChange={(e) => onGrowthChange(e.target.value)}
                    className="ticker-input"
                    style={{ width: 80, marginLeft: 8 }}
                  />
                </label>
                <button onClick={onApplyAssumptions} className="primary" style={{ marginLeft: 12 }}>
                  Apply
                </button>
              </div>
              <table className="matrix">
                <tbody>
                  <tr>
                    <td className="row-label">Base year FCF</td>
                    <td>{fmtMoney(dcf.fcf)}</td>
                  </tr>
                  <tr>
                    <td className="row-label">Discount rate</td>
                    <td>{formatPercent(dcf.discount_rate)}</td>
                  </tr>
                  <tr>
                    <td className="row-label">Growth</td>
                    <td>{formatPercent(dcf.growth)}</td>
                  </tr>
                  <tr>
                    <td className="row-label">Net debt</td>
                    <td>{fmtMoney(dcf.net_debt)}</td>
                  </tr>
                  <tr>
                    <td className="row-label">Intrinsic value / share</td>
                    <td>
                      <strong>
                        {dcf.equity_value_per_share === null
                          ? "—"
                          : formatMoney(dcf.equity_value_per_share)}
                      </strong>
                      {valuation.multiples.price !== null &&
                        dcf.equity_value_per_share !== null && (
                          <span className="meta-text">
                            {" "}
                            vs price {formatMoney(valuation.multiples.price)} (
                            {formatPercent(
                              dcf.equity_value_per_share / valuation.multiples.price - 1
                            )}{" "}
                            upside)
                          </span>
                        )}
                    </td>
                  </tr>
                </tbody>
              </table>
              {dcf.diverges && (
                <p className="meta-text">
                  The perpetuity diverges: growth must stay below the discount rate. Raise the
                  discount rate or lower the growth assumption to get a finite value.
                </p>
              )}
              <h3>Sensitivity · equity value per share (discount rate × growth)</h3>
              <table className="matrix">
                <thead>
                  <tr>
                    <th className="row-label">Rate ↓ / Growth →</th>
                    {dcf.sensitivity.growth_rates.map((g) => (
                      <th key={g}>{formatPercent(g)}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {dcf.sensitivity.rows.map((row) => (
                    <tr key={row.discount_rate}>
                      <td className="row-label">{formatPercent(row.discount_rate)}</td>
                      {dcf.sensitivity.growth_rates.map((g) => {
                        const value = row.values[g];
                        return (
                          <td key={g}>{value === null ? "—" : formatMoney(value)}</td>
                        );
                      })}
                    </tr>
                  ))}
                </tbody>
              </table>
            </section>
          )}

          <section className="matrix-block">
            <h2>Current multiples · FY{valuation.multiples.fiscal_year ?? ""}</h2>
            <table className="matrix">
              <tbody>
                <tr>
                  <td className="row-label">Price</td>
                  <td>{fmtMoney(valuation.multiples.price)}</td>
                </tr>
                <tr>
                  <td className="row-label">Market cap</td>
                  <td>{fmtMoney(valuation.multiples.market_cap)}</td>
                </tr>
                <tr>
                  <td className="row-label">P/E</td>
                  <td>{fmtMultiple(valuation.multiples.pe)}</td>
                </tr>
                <tr>
                  <td className="row-label">EV/EBITDA</td>
                  <td>{fmtMultiple(valuation.multiples.ev_ebitda)}</td>
                </tr>
                <tr>
                  <td className="row-label">FCF yield</td>
                  <td>{fmtPct(valuation.multiples.fcf_yield)}</td>
                </tr>
              </tbody>
            </table>
          </section>

          {valuation.history.length > 0 && (
            <section className="matrix-block">
              <h2>Own history · multiples at each fiscal year-end price</h2>
              <table className="matrix">
                <thead>
                  <tr>
                    <th className="row-label">Fiscal year</th>
                    <th>Price</th>
                    <th>P/E</th>
                    <th>EV/EBITDA</th>
                    <th>FCF yield</th>
                  </tr>
                </thead>
                <tbody>
                  {valuation.history.map((row) => (
                    <tr key={row.fiscal_year}>
                      <td className="row-label">
                        FY{row.fiscal_year}
                        <span className="meta-text"> · {row.end_date}</span>
                      </td>
                      <td>{fmtMoney(row.price)}</td>
                      <td>{fmtMultiple(row.pe)}</td>
                      <td>{fmtMultiple(row.ev_ebitda)}</td>
                      <td>{fmtPct(row.fcf_yield)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </section>
          )}

          {valuation.peers.length > 0 && (
            <section className="matrix-block">
              <h2>Peers · current multiples</h2>
              <table className="matrix">
                <thead>
                  <tr>
                    <th className="row-label">Peer</th>
                    <th>FY</th>
                    <th>Price</th>
                    <th>P/E</th>
                    <th>EV/EBITDA</th>
                    <th>FCF yield</th>
                  </tr>
                </thead>
                <tbody>
                  {valuation.peers.map((peer) => (
                    <tr key={peer.ticker}>
                      <td className="row-label">{peer.ticker}</td>
                      <td>{peer.fiscal_year ?? "—"}</td>
                      <td>{fmtMoney(peer.price)}</td>
                      <td>{fmtMultiple(peer.pe)}</td>
                      <td>{fmtMultiple(peer.ev_ebitda)}</td>
                      <td>{fmtPct(peer.fcf_yield)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </section>
          )}
        </>
      )}
    </section>
  );
}
