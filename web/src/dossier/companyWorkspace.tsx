import type { ReactNode } from "react";
import { DOSSIER_STEPS, gateStatusChip, stepIsDone, stepLockReason } from "./steps";
import type { Dossier } from "./useDossier";
import { DossierStrip, LockedStepNote } from "./dossierStrip";
import { OnePagerStepPanel } from "./onePagerStepPanel";
import { BusinessSwotStepPanel } from "./businessSwotStepPanel";
import { FinancialsStepPanel } from "./financialsStepPanel";
import { StrategyStepPanel } from "./strategyStepPanel";
import { ValuationStepPanel } from "./valuationStepPanel";
import { ThesisStepPanel } from "./thesisStepPanel";
import { ArrowLeftIcon } from "./icons";

function statusLabel(gate: { status: string } | null): { text: string; kind: string } {
  const status = gate?.status === "accepted" || gate?.status === "rejected" ? gate.status : null;
  return gateStatusChip(status);
}

export function CompanyWorkspace({
  ticker,
  activeStep,
  onSelectStep,
  onBack,
  backLabel,
  onOpenNumbers,
  onQuotaChange,
  dossier,
  saved,
  saveBusy,
  saveError,
  onSaveToLibrary,
  onUnsaveFromLibrary,
}: {
  ticker: string;
  activeStep: number;
  onSelectStep: (n: number) => void;
  onBack: () => void;
  backLabel: string;
  onOpenNumbers: () => void;
  onQuotaChange: () => void;
  dossier: Dossier;
  saved: boolean;
  saveBusy: boolean;
  saveError: string;
  onSaveToLibrary: () => void;
  onUnsaveFromLibrary: () => void;
}) {
  const gate = dossier.progress?.gate ?? dossier.onePager?.gate ?? null;
  const done = dossier.progress?.done ?? {};
  const reason = stepLockReason(activeStep, gate, done);
  const stepInfo = DOSSIER_STEPS[activeStep - 1] ?? DOSSIER_STEPS[0];
  const status = statusLabel(gate);

  const toggleStepDone = (step: number) => (doneNow: boolean) =>
    dossier.toggleDone(ticker, step, doneNow);

  let content: ReactNode;
  if (reason) {
    content = <LockedStepNote step={stepInfo} reason={reason} />;
  } else if (activeStep === 1) {
    content = (
      <OnePagerStepPanel
        ticker={ticker}
        onOpenIngest={onBack}
        response={dossier.onePager}
        loading={dossier.onePagerLoading}
        error={dossier.onePagerError}
        onLoad={dossier.loadOnePager}
        onGate={(decision) => dossier.setGate(ticker, decision)}
      />
    );
  } else if (activeStep === 2) {
    content = (
      <BusinessSwotStepPanel
        ticker={ticker}
        onOpenIngest={onBack}
        response={dossier.business}
        loading={dossier.businessLoading}
        error={dossier.businessError}
        onLoad={dossier.loadBusinessSwot}
        done={stepIsDone(2, gate, done)}
        onToggleDone={toggleStepDone(2)}
      />
    );
  } else if (activeStep === 3) {
    content = (
      <FinancialsStepPanel
        ticker={ticker}
        onOpenIngest={onBack}
        response={dossier.financials}
        loading={dossier.financialsLoading}
        error={dossier.financialsError}
        onLoad={dossier.loadFinancials}
        onQuotaChange={onQuotaChange}
        done={stepIsDone(3, gate, done)}
        onToggleDone={toggleStepDone(3)}
      />
    );
  } else if (activeStep === 4) {
    content = (
      <StrategyStepPanel
        ticker={ticker}
        onOpenIngest={onBack}
        response={dossier.strategy}
        loading={dossier.strategyLoading}
        error={dossier.strategyError}
        onLoad={dossier.loadStrategy}
        done={stepIsDone(4, gate, done)}
        onToggleDone={toggleStepDone(4)}
      />
    );
  } else if (activeStep === 5) {
    content = (
      <ValuationStepPanel
        ticker={ticker}
        onOpenIngest={onBack}
        response={dossier.valuation}
        loading={dossier.valuationLoading}
        error={dossier.valuationError}
        onLoad={dossier.loadValuation}
        valDiscountPct={dossier.valDiscountPct}
        valGrowthPct={dossier.valGrowthPct}
        onDiscountChange={dossier.setValDiscountPct}
        onGrowthChange={dossier.setValGrowthPct}
      />
    );
  } else {
    content = (
      <ThesisStepPanel
        ticker={ticker}
        onOpenIngest={onBack}
        response={dossier.thesis}
        loading={dossier.thesisLoading}
        error={dossier.thesisError}
        onLoad={dossier.loadThesis}
        saved={saved}
        saveBusy={saveBusy}
        saveError={saveError}
        onSaveToLibrary={onSaveToLibrary}
        onUnsaveFromLibrary={onUnsaveFromLibrary}
      />
    );
  }

  return (
    <div className="page workspace-page">
      <div className="workspace-head">
        <button type="button" className="workspace-back" onClick={onBack}>
          <ArrowLeftIcon size={15} />
          {backLabel}
        </button>
        <div className="workspace-title">
          <h1>{ticker}</h1>
          <span className="sub">Six-step dossier</span>
          <span className={`status-chip status-${status.kind}`}>{status.text}</span>
        </div>
        <div className="workspace-actions">
          <button type="button" className="btn btn-secondary btn-sm" onClick={onOpenNumbers}>
            Numbers view
          </button>
        </div>
      </div>

      <div className="dossier-doc">
        <DossierStrip
          gate={gate}
          done={done}
          activeStep={activeStep}
          onSelect={onSelectStep}
        />
        {dossier.progressLoading && (
          <div className="dossier-body">
            <div className="status">
              <span className="spinner" aria-hidden="true" />
              <span>Loading dossier progress…</span>
            </div>
          </div>
        )}
        {!dossier.progressLoading && dossier.progressError && (
          <div className="dossier-body">
            <div className="error-banner">{dossier.progressError}</div>
          </div>
        )}
        {!dossier.progressLoading && !dossier.progressError && (
          <div className="dossier-body">{content}</div>
        )}
      </div>
    </div>
  );
}
