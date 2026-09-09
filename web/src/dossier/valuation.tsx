import type { ValuationResponse } from "../api";
import { formatMoney, formatPercent } from "./format";

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
  onApplyAssumptions,
}: {
  response: ValuationResponse;
  discountPct: string;
  growthPct: string;
  onDiscountChange: (value: string) => void;
  onGrowthChange: (value: string) => void;
  onApplyAssumptions: () => void;
}) {
  const valuation = response.valuation ?? null;
  const dcf = valuation?.dcf ?? null;

  return (
    <div className="report-view">
      <div className="report-meta">
        <span>
          Valuation sits after your earlier analysis so the price cannot bias
          Steps 2-4.
        </span>
      </div>

      {!valuation ? (
        <div className="status">Valuation is locked until the dossier is ready.</div>
      ) : (
        <>
          {dcf && (
            <section className="matrix-block">
              <h2>DCF · single-stage growing perpetuity</h2>
              <div className="price-card">
                <div className="assumption-row">
                  <label className="assumption-label">
                    Discount rate (%)
                    <input
                      value={discountPct}
                      onChange={(e) => onDiscountChange(e.target.value)}
                      className="text-input ticker-input"
                      inputMode="decimal"
                    />
                  </label>
                  <label className="assumption-label">
                    Growth (%)
                    <input
                      value={growthPct}
                      onChange={(e) => onGrowthChange(e.target.value)}
                      className="text-input ticker-input"
                      inputMode="decimal"
                    />
                  </label>
                  <button onClick={onApplyAssumptions} className="btn btn-primary btn-sm">
                    Apply
                  </button>
                </div>
              </div>
              <div className="matrix-scroll">
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
              </div>
              {dcf.diverges && (
                <p className="meta-text">
                  The perpetuity diverges: growth must stay below the discount rate. Raise the
                  discount rate or lower the growth assumption to get a finite value.
                </p>
              )}
              <h3 className="table-caption">
                Sensitivity · equity value per share (discount rate × growth)
              </h3>
              <div className="matrix-scroll">
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
              </div>
            </section>
          )}

          <section className="matrix-block">
            <h2>Current multiples · FY{valuation.multiples.fiscal_year ?? ""}</h2>
            <div className="metric-card">
              <div className="metric-main">
                <span className="metric-label">Price</span>
                <span className="metric-value">{fmtMoney(valuation.multiples.price)}</span>
              </div>
              <div className="metric-grid">
                <div className="metric-cell">
                  <span className="metric-label">Market cap</span>
                  <span className="metric-value">{fmtMoney(valuation.multiples.market_cap)}</span>
                </div>
                <div className="metric-cell">
                  <span className="metric-label">P/E</span>
                  <span className="metric-value">{fmtMultiple(valuation.multiples.pe)}</span>
                </div>
                <div className="metric-cell">
                  <span className="metric-label">EV/EBITDA</span>
                  <span className="metric-value">{fmtMultiple(valuation.multiples.ev_ebitda)}</span>
                </div>
                <div className="metric-cell">
                  <span className="metric-label">FCF yield</span>
                  <span className="metric-value">{fmtPct(valuation.multiples.fcf_yield)}</span>
                </div>
              </div>
            </div>
          </section>

          {valuation.history.length > 0 && (
            <section className="matrix-block">
              <h2>Own history · multiples at each fiscal year-end price</h2>
              <div className="matrix-scroll">
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
              </div>
            </section>
          )}

          {valuation.peers.length > 0 && (
            <section className="matrix-block">
              <h2>Peers · current multiples</h2>
              <div className="matrix-scroll">
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
              </div>
            </section>
          )}
        </>
      )}
    </div>
  );
}
