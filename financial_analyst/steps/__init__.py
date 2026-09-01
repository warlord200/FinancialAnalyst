"""The six dossier steps. T4 implements step 1 (the one-pager); T5 adds
the source-tagged artifact framework and step 2 (Business & SWOT); T6 adds
step 3 (Financials); T7 adds step 4 (Strategy); T8 adds step-scoped chat.

``STEP_SCOPES`` maps each step that drafts over the corpus to the filing
Items it draws on: step 2 reads Item 1/1A, step 3 reads Item 7/8, step 4
reads Item 5/7. Steps 1, 5, and 6 derive from the numbers layer rather
than the corpus, so they have no chat scope (chat is unsupported there).
"""

STEP_ONE = 1

STEP_SCOPES = {
    2: ("ITEM 1", "ITEM 1A"),
    3: ("ITEM 7", "ITEM 8"),
    4: ("ITEM 5", "ITEM 7"),
}
