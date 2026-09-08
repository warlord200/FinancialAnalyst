import type { ArtifactSection, FinancialTable, SourceTag, TableUnit } from "../api";
import { formatPercent } from "./format";

export function sourceTagLabel(tag: SourceTag) {
  if (tag.type === "fiscal_year") return `FY${tag.value}`;
  return tag.value;
}

export function ArtifactSectionCard({ section }: { section: ArtifactSection }) {
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

export function formatTableValue(value: number | null, unit: TableUnit) {
  if (value === null) return "—";
  if (unit === "percent") return formatPercent(value);
  return value.toFixed(2);
}

export function FinancialsTableCard({ table }: { table: FinancialTable }) {
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
