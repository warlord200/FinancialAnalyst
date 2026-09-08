import type { ThesisResponse } from "../api";
import { sourceTagLabel } from "./artifacts";

export function ThesisPanel({ response }: { response: ThesisResponse }) {
  const thesis = response.thesis ?? null;

  const draftByKey = new Map(
    (response.draft?.sections ?? []).map((s) => [s.key, s])
  );

  return (
    <section>
      <div className="report-meta">
        <span className="meta-text">
          Step 6 · Thesis · {response.ticker} · opens once the one-pager is
          accepted and Steps 2-4 are marked done, so the thesis follows the
          whole dossier.
        </span>
      </div>

      {!thesis ? (
        <div className="status">
          Thesis locked. Accept the one-pager (Step 1) and mark Steps 2-4
          done to draft your thesis.
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
