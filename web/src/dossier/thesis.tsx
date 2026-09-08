import type { ThesisResponse } from "../api";
import { sourceTagLabel } from "./artifacts";
import { VALUATION_STEP_LABELS } from "./valuation";

export function ThesisPanel({
  response,
  onToggleDone,
}: {
  response: ThesisResponse;
  onToggleDone: (step: number, done: boolean) => void;
}) {
  const thesis = response.thesis ?? null;

  const draftByKey = new Map(
    (response.draft?.sections ?? []).map((s) => [s.key, s])
  );

  return (
    <section>
      <div className="report-meta">
        <span className="meta-text">
          Step 6 · Thesis · {response.ticker} · locked until you mark steps
          1-4 done, so the thesis follows the whole dossier.
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

      {!thesis ? (
        <div className="status">
          Thesis locked. Finish reviewing the steps above to draft your
          thesis.
        </div>
      ) : (
        <div className="thesis-editor">
          {thesis.sections.map((section) => {
            const draft = draftByKey.get(section.key);
            return (
              <section key={section.key} className="matrix-block">
                <h2>{section.heading}</h2>
                <div className="artifact-content">{section.content}</div>
                {draft && draft.sources.length > 0 && (
                  <>
                    <div className="source-tags">
                      <span className="meta-text">Draft grounding · </span>
                      {draft.sources.map((tag, i) => (
                        <span
                          key={i}
                          className={`source-tag source-${tag.type}`}
                        >
                          {sourceTagLabel(tag)}
                        </span>
                      ))}
                    </div>
                    {draft.evidence.length > 0 && (
                      <details className="evidence-block">
                        <summary>Draft source quotes</summary>
                        <ul>
                          {draft.evidence.map((quote, i) => (
                            <li key={i}>"{quote}"</li>
                          ))}
                        </ul>
                      </details>
                    )}
                  </>
                )}
              </section>
            );
          })}
        </div>
      )}
    </section>
  );
}
