import { useCallback, useEffect, useState } from "react";
import { clearPeers, getPeers, setPeers } from "../api";
import type { FinancialTable } from "../api";
import { FinancialsTableCard } from "./artifacts";
import { CloseIcon } from "./icons";

export function PeerScorecardPanel({
  ticker,
  onQuotaChange,
}: {
  ticker: string;
  onQuotaChange: () => void;
}) {
  const [peers, setPeersList] = useState<string[]>([]);
  const [scorecard, setScorecard] = useState<FinancialTable[]>([]);
  const [input, setInput] = useState("");
  const [error, setError] = useState("");
  const [loaded, setLoaded] = useState(false);
  const [busy, setBusy] = useState(false);

  const refresh = useCallback(async () => {
    setError("");
    try {
      const res = await getPeers(ticker);
      setPeersList(res.peers);
      setScorecard(res.scorecard);
      setLoaded(true);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load peer scorecard");
    }
  }, [ticker]);

  useEffect(() => {
    setLoaded(false);
    setPeersList([]);
    setScorecard([]);
    refresh();
  }, [refresh]);

  async function save(nextPeers: string[]) {
    setBusy(true);
    setError("");
    try {
      const res = await setPeers(ticker, nextPeers);
      setPeersList(res.peers);
      setScorecard(res.scorecard);
      onQuotaChange();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to save peers");
    } finally {
      setBusy(false);
    }
  }

  function addPeer() {
    const peer = input.trim().toUpperCase();
    if (!peer || busy) return;
    setInput("");
    if (!peers.includes(peer)) {
      save([...peers, peer]);
    }
  }

  return (
    <section className="peer-panel">
      <div className="panel-title">
        <span>Peer scorecard</span>
        {loaded && <span className="quota-value">{peers.length} peers</span>}
      </div>
      <p className="step-scope" style={{ marginBottom: 4 }}>
        {ticker} vs its peers · growth, margins, debt, and returns, latest
        fiscal year each
      </p>
      <div className="peer-add-row">
        <input
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && addPeer()}
          placeholder="Add a peer ticker (e.g. F)"
          className="text-input ticker-input"
          style={{ maxWidth: 210 }}
          aria-label="Add a peer ticker"
        />
        <button onClick={addPeer} disabled={busy || !input.trim()} className="btn btn-secondary btn-sm">
          Add peer
        </button>
        {peers.length > 0 && (
          <button
            onClick={() => {
              setBusy(true);
              setError("");
              clearPeers(ticker)
                .then((res) => {
                  setPeersList(res.peers);
                  setScorecard(res.scorecard);
                })
                .catch((e) => setError(e instanceof Error ? e.message : "Failed to clear peers"))
                .finally(() => setBusy(false));
            }}
            disabled={busy}
            className="link-button"
          >
            Clear all
          </button>
        )}
      </div>
      {error && <div className="error-banner">{error}</div>}
      {peers.length > 0 && (
        <div className="peer-list">
          {peers.map((peer) => (
            <span key={peer} className="peer-chip">
              {peer}
              <button
                onClick={() => save(peers.filter((p) => p !== peer))}
                disabled={busy}
                aria-label={`Remove peer ${peer}`}
              >
                <CloseIcon size={11} strokeWidth={2.4} />
              </button>
            </span>
          ))}
        </div>
      )}
      {scorecard.length > 0 ? (
        scorecard.map((table) => <FinancialsTableCard key={table.key} table={table} />)
      ) : (
        <p className="peer-empty">
          Add peer tickers to compare {ticker}'s growth, margins, debt, and
          returns against theirs.
        </p>
      )}
    </section>
  );
}
