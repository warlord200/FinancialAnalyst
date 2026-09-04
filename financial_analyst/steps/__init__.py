"""The six dossier steps. T4 implements step 1 (the one-pager); T5 adds
the source-tagged artifact framework and step 2 (Business & SWOT); T6 adds
step 3 (Financials); T7 adds step 4 (Strategy); T8 adds step-scoped chat;
T10 adds the step 3 peer scorecard (per-user peer lists compared against
the target on growth, margins, debt, and returns, all from the numbers
layer); T11 adds step 5 (Valuation): a numbers-derived DCF with a
sensitivity table plus market multiples against the company's own history
and its peers, hard-gated behind per-user done-marks on steps 1-4; T12
adds step 6 (Thesis): a drafted, editable, per-user thesis (what I hold,
why, key assumptions, what would change my mind) plus a corpus-grounded
devil's-advocate section and open research gaps, persisted so reopening
the ticker and re-analysis keep it. Step 6 is gated on the same done-marks
as valuation.

``STEP_SCOPES`` maps each step that drafts over the corpus to the filing
Items it draws on: step 2 reads Item 1/1A, step 3 reads Item 7/8, step 4
reads Item 5/7. Steps 1 and 5 derive from the numbers layer rather than
the corpus, so they have no chat scope (chat is unsupported there). Step 6
(the thesis) drafts over every Item the dossier reads, so it also has no
step chat scope.
"""

STEP_ONE = 1

# Steps the user must mark done before valuation (step 5) unlocks. The
# accept/reject gate on step 1 is deliberately NOT one of these: a done mark
# means "I reviewed this step", which is the user's own signal that they are
# ready to see the price-based analysis.
VALUATION_GATE_STEPS = (1, 2, 3, 4)

STEP_SCOPES = {
    2: ("ITEM 1", "ITEM 1A"),
    3: ("ITEM 7", "ITEM 8"),
    4: ("ITEM 5", "ITEM 7"),
}
