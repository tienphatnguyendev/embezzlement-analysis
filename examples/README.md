# Authored teaching fixtures

These records were created for this repository. They are not real banking records or a subset of IBM's data. The column format is IBM-compatible so the entire pipeline runs offline.

Scenario A: `VICTIM → INTERMEDIARY → PERSONAL → PERSONAL_SAVINGS`. The supplied context says the personal-account holder works for the originating company. This is a review lead. No fixture invoice or authorization record proves that the intermediary is fictitious or that the payment was unauthorized.

Scenario B: `VICTIM → SUPPLIER → SUPPLIER_WORKER`. This represents an ordinary supplier using revenue to pay a worker. It intentionally passes the same timing/amount filters. Its recipient works for the supplier, not the originating buyer.

Additional rows test a payment before the incoming transfer, incompatible currency, and a payment outside the window. Labels are deliberately independent of these narratives, to show the search does not use the label column. Do not score these labels as fraud ground truth.

The default search returns three paths: Scenario A's two-hop prefix, its three-hop extension, and Scenario B's two-hop chain. Two outputs overlap. They are not three independent incidents and cannot be summed as loss.
