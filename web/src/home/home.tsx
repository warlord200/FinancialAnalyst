import { useEffect, useRef, type ReactNode, type Ref } from "react";
import {
  BrandMark,
  CheckIcon,
  DocumentIcon,
  LockIcon,
  SearchIcon,
} from "../dossier/icons";

function useReveal<T extends HTMLElement>() {
  const ref = useRef<T | null>(null);
  useEffect(() => {
    const node = ref.current;
    if (!node || typeof IntersectionObserver === "undefined") return;
    const show = () => node.classList.add("rv-in");
    const viewport = window.innerHeight || document.documentElement.clientHeight;
    const rect = node.getBoundingClientRect();
    if (rect.bottom > 0 && rect.top < viewport) {
      show();
      return;
    }
    node.classList.add("rv-enter");
    const observer = new IntersectionObserver(
      (entries) => {
        for (const entry of entries) {
          if (entry.isIntersecting) {
            show();
            observer.unobserve(entry.target);
          }
        }
      },
      { rootMargin: "0px 0px -8% 0px", threshold: 0 }
    );
    observer.observe(node);
    return () => observer.disconnect();
  }, []);
  return ref;
}

function HeroDossier() {
  const steps = [
    { n: 1, name: "One-pager", orb: <CheckIcon />, classes: "step-tab done", sub: "decision made" },
    { n: 2, name: "Business & SWOT", orb: "2", classes: "step-tab active", sub: "in progress" },
    { n: 3, name: "Financials", orb: "3", classes: "step-tab", sub: "in progress" },
    { n: 4, name: "Strategy", orb: "4", classes: "step-tab", sub: "in progress" },
    { n: 5, name: "Valuation", orb: <LockIcon />, classes: "step-tab locked", sub: "mark Steps 2-4 done" },
    { n: 6, name: "Thesis", orb: <LockIcon />, classes: "step-tab locked", sub: "mark Steps 2-4 done" },
  ];
  return (
    <figure className="home-dossier">
      <div className="home-dossier-head">
        <span className="ticker">MSFT</span>
        <span className="sub">Six-step dossier</span>
        <span className="status-chip status-accepted">Accepted</span>
      </div>
      <div className="dossier-doc home-dossier-doc">
        <ol className="strip" aria-label="Sample dossier steps">
          {steps.map((s) => (
            <li key={s.n} className={s.classes} aria-current={s.classes.includes("active")}>
              <span className="step-top">
                <span className="step-orb">{s.orb}</span>
              </span>
              <span className="step-name">{s.name}</span>
              <span className="step-sub">{s.sub}</span>
            </li>
          ))}
        </ol>
        <div className="dossier-body">
          <div className="report-view">
            <div className="report-meta">
              <span>Business &amp; SWOT · MSFT · FY2026</span>
            </div>
            <section className="artifact-section">
              <h2>Business Overview</h2>
              <p className="artifact-content">
                Microsoft is a technology company that develops and supports a broad portfolio of
                software, services, devices, and solutions, including operating systems, server
                applications, business solution applications, and video games, as well as
                cloud-based solutions providing AI, software, services, platforms, and content. The
                company operates through three segments: Productivity and Business Processes,
                Intelligent Cloud, and More Personal Computing.
              </p>
              <div className="source-tags">
                <span className="tags-label">Sources</span>
                <span className="source-tag source-item">ITEM 1</span>
                <span className="source-tag source-fiscal_year">FY2026</span>
                <span className="source-tag source-filing">10-K</span>
              </div>
              <details className="evidence-block" open>
                <summary>Source quotes</summary>
                <ul>
                  <li>
                    “We develop and support a broad portfolio of technology solutions for
                    individuals and businesses, focusing on secure, trusted, and innovative
                    platforms and applications…”
                  </li>
                </ul>
              </details>
            </section>
          </div>
        </div>
      </div>
      <figcaption className="home-dossier-note">
        Sample dossier · Microsoft (MSFT), FY2026 — real engine output from its SEC filings.
      </figcaption>
    </figure>
  );
}

function MethodRow({ n, name, scope }: { n: number; name: string; scope: string }) {
  return (
    <li className="method-row">
      <span className="method-orb">{n}</span>
      <span className="method-body">
        <span className="method-name">{name}</span>
        <span className="method-scope">{scope}</span>
      </span>
    </li>
  );
}

const METHOD_STEPS = [
  { n: 1, name: "One-pager", scope: "growth, profitability, debt — from the parsed numbers" },
  { n: 2, name: "Business & SWOT", scope: "Item 1 & 1A — the business and its risks in a four-way SWOT" },
  { n: 3, name: "Financials", scope: "Item 7 & 8 — statements, common-size tables, ratios, CAGR" },
  { n: 4, name: "Strategy", scope: "Item 5 & 7 — capital allocation and the plan forward" },
  { n: 5, name: "Valuation", scope: "from the parsed numbers — a price read" },
  { n: 6, name: "Thesis", scope: "the read-only, source-tagged conclusion" },
];

const METRIC_ROWS = [
  { config: "Vector", mrr: "0.794", hit: "0.937", ndcg: "0.830" },
  { config: "Hybrid (default)", mrr: "0.802", hit: "0.940", ndcg: "0.837" },
];

function ClaimProof({ figureRef }: { figureRef?: Ref<HTMLElement> }) {
  return (
    <figure ref={figureRef} className="proof-card card rv-rise rv-delay-1">
      <div className="report-meta">
        <span>MSFT · FY2026</span>
      </div>
      <section className="artifact-section">
        <h2>Opportunities</h2>
        <p className="artifact-content">
          Microsoft identifies significant future opportunities in leading the AI platform wave and
          helping customers maximize value from their digital spend through the Microsoft Cloud.
        </p>
        <div className="source-tags">
          <span className="tags-label">Sources</span>
          <span className="source-tag source-item">ITEM 1</span>
          <span className="source-tag source-fiscal_year">FY2026</span>
          <span className="source-tag source-filing">10-K</span>
        </div>
        <details className="evidence-block">
          <summary>Source quotes</summary>
          <ul>
            <li>
              “We are focused on helping customers use the breadth and depth of the Microsoft Cloud
              to get the most value out of their digital spend while leading the AI platform wave…”
            </li>
          </ul>
        </details>
      </section>
    </figure>
  );
}

function FeatureRow({
  icon,
  title,
  children,
}: {
  icon: ReactNode;
  title: string;
  children: ReactNode;
}) {
  return (
    <div className="feature-row">
      <span className="feature-icon">{icon}</span>
      <div className="feature-copy">
        <h3>{title}</h3>
        <p>{children}</p>
      </div>
    </div>
  );
}

export function HomePage({
  onGetStarted,
  onLogIn,
}: {
  onGetStarted: () => void;
  onLogIn: () => void;
}) {
  const methodHeadRef = useReveal<HTMLDivElement>();
  const methodListRef = useReveal<HTMLOListElement>();
  const proofHeadRef = useReveal<HTMLDivElement>();
  const proofStackRef = useReveal<HTMLDivElement>();
  const proofCardRef = useReveal<HTMLElement>();
  const measureHeadRef = useReveal<HTMLDivElement>();
  const measureCardRef = useReveal<HTMLDivElement>();
  const closeRef = useReveal<HTMLDivElement>();
  return (
    <div className="home">
      <header className="home-topbar">
        <div className="home-topbar-inner">
          <span className="brand">
            <span className="brand-mark">
              <BrandMark />
            </span>
            <span className="brand-text">
              <span className="brand-name">ThetaRadar</span>
              <span className="brand-desc">Financial Analyst</span>
            </span>
          </span>
          <nav className="home-nav" aria-label="Sections">
            <a href="#method">The method</a>
            <a href="#proof">Grounding</a>
            <a href="#measured">Measured</a>
          </nav>
          <span className="home-actions">
            <button type="button" className="btn btn-ghost btn-sm" onClick={onLogIn}>
              Log in
            </button>
            <button type="button" className="btn btn-primary btn-sm" onClick={onGetStarted}>
              Get started
            </button>
          </span>
        </div>
      </header>

      <main className="home-main">
        <section className="home-hero">
          <div className="home-hero-copy">
            <h1>A stock thesis that shows its work.</h1>
            <p className="home-lede">
              One fixed six-step dossier from the company's own SEC filings — every claim
              source-tagged, not a chat.
            </p>
            <div className="home-cta-row">
              <button type="button" className="btn btn-primary btn-lg" onClick={onGetStarted}>
                Start your first dossier
              </button>
              <a className="btn btn-secondary btn-lg" href="#method">
                See the method
              </a>
            </div>
          </div>
          <HeroDossier />
        </section>

        <section className="home-section" id="method">
          <div className="home-section-head rv-rise" ref={methodHeadRef}>
            <h2>The six steps, in order.</h2>
          </div>
          <ol ref={methodListRef} className="method-list rv-list">
            {METHOD_STEPS.map((s) => (
              <MethodRow key={s.n} {...s} />
            ))}
          </ol>
          <p className="home-section-foot">
            Accept the one-pager or reject it — then mark steps 2-4 done to unlock 5 and 6.
          </p>
        </section>

        <section className="home-band" id="proof">
          <div className="home-section-head rv-rise" ref={proofHeadRef}>
            <h2>Grounding you can check.</h2>
          </div>
          <div className="proof-layout">
            <div className="feature-stack rv-rise" ref={proofStackRef}>
              <FeatureRow icon={<DocumentIcon size={20} />} title="Scoped to the filing">
                Each step reads only the sections of the company's own 10-K that belong to it.
              </FeatureRow>
              <FeatureRow icon={<SearchIcon size={20} />} title="Hybrid retrieval">
                Dense embeddings and BM25 are fused by reciprocal-rank fusion over the per-company
                corpus, so keyword and meaning both count.
              </FeatureRow>
              <FeatureRow icon={<CheckIcon size={20} />} title="Validated before shown">
                Generated artifacts are checked against their sources before they reach you; a
                draft that cannot be grounded is not displayed.
              </FeatureRow>
            </div>
            <ClaimProof figureRef={proofCardRef} />
          </div>
        </section>

        <section className="home-section" id="measured">
          <div className="home-section-head rv-rise" ref={measureHeadRef}>
            <h2>Measured, not claimed.</h2>
            <p>
              Retrieval quality is evaluated per configuration on real questions. These are the
              aggregate numbers, and the full config-by-config tables live in the repo.
            </p>
          </div>
          <div className="card table-card measure-card rv-rise" ref={measureCardRef}>
            <div className="measure-head">
              <h3>Aggregate retrieval · Microsoft + Tesla corpora</h3>
              <span className="card-hint">331 queries · 4/9/2026</span>
            </div>
            <table className="data-table measure-table">
              <thead>
                <tr>
                  <th>Config</th>
                  <th className="num">MRR</th>
                  <th className="num">Hit rate</th>
                  <th className="num">NDCG</th>
                </tr>
              </thead>
              <tbody>
                {METRIC_ROWS.map((r) => (
                  <tr key={r.config}>
                    <td>{r.config}</td>
                    <td className="num">{r.mrr}</td>
                    <td className="num">{r.hit}</td>
                    <td className="num">{r.ndcg}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>

        <section className="home-close">
          <div className="home-close-inner rv-rise" ref={closeRef}>
            <h2>Start with the ticker you keep meaning to research.</h2>
            <p>
              One sitting, or a few days: from a US-listed company you are curious about to a
              source-tagged thesis you saved in your Library.
            </p>
            <div className="home-cta-row">
              <button type="button" className="btn btn-primary btn-lg" onClick={onGetStarted}>
                Start your first dossier
              </button>
            </div>
            <button type="button" className="btn btn-ghost btn-sm" onClick={onLogIn}>
              Log in
            </button>
            <p className="home-hero-meta">
              Email + password · Free tier: 3 analyses and 30 chat rounds a day.
            </p>
          </div>
        </section>
      </main>

      <footer className="home-footer">
        <div className="home-footer-inner">
          <span className="brand">
            <span className="brand-mark">
              <BrandMark size={22} />
            </span>
            <span className="brand-text">
              <span className="brand-name">ThetaRadar</span>
              <span className="brand-desc">Financial Analyst</span>
            </span>
          </span>
          <p className="home-footer-note">
            Grounded investment research from SEC filings. For research, not financial advice.
          </p>
        </div>
      </footer>
    </div>
  );
}
