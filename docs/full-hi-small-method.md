# Full HI-Small run method

The requested run downloads the complete publisher transaction, account and laundering-pattern files. Each raw file is retained with its URL, retrieval time, byte count and SHA-256. The full transaction import uses a separate database from the authored demo and the earlier prefix.

## Detection scope

With no specified victim account, scan every observable **business → business → person** chain of two transactions. Require strictly increasing timestamps, a total elapsed time at most 72 hours, matching currency at the intermediary, and an onward-paid/incoming-received amount ratio between 0.80 and 1.05 inclusive. Use exact arithmetic. Require distinct bank/account identities and distinct entity IDs, and count excluded same-owner cases separately. Entity roles are derived from IBM's synthetic names, not confirmed company structures. An intermediary business is not automatically a shell company.

Evaluate this predefined hypothesis over the complete accepted transaction graph. Stream all selected candidate chains to JSONL, record examined counts and coverage, and publish completed files atomically. A few deterministic examples help review; they do not replace the complete candidate output.

## Independent checks

An independent CSV audit verifies row counts, account joins, dates, currencies, and pattern-file structure. The importer separately validates every amount as positive and finite. Laundering labels and pattern membership remain outside candidate selection. After selection, compare selected edge IDs and paths with the binary laundering labels. Report whole-dataset and main-window/tail counts separately when appropriate; this is a retrospective descriptive evaluation, not a train/test benchmark.

Measured version-8 results contradict the publisher's literal all-laundering tail statement: 655 of 1,108 post-main-window rows are label 1 and 453 are label 0. Preserve both populations. The ledger-wide scan completed with 905 candidates, no truncation, and zero laundering-labeled selected edges; see the local findings report for interpretation.

The two-hop hypothesis does not cover longer chains, splitting/merging, equal-minute transfers or unknown entity roles. Example three-hop traces, if produced, have their own explicit coverage and caps. Never describe example traces as an exhaustive longer-path search.

## Missing business evidence

The IBM files do not supply employee/vendor master snapshots, invoices, purchase orders, delivery receipts, approval records, confirmed shell status, or embezzlement-case outcomes. The full-data report marks these ACFE checks as unavailable. The authored demo is not used to fill these evidence gaps. Candidate amounts are not summed into losses; overlapping paths can share transactions and accounts can mix funds.

## Reproducibility and interpretation

Retain detector parameters, source fingerprints, code version, duration, row references, and completion status. Label comparisons evaluate only the laundering label under IBM's simulator. They do not measure confirmed embezzlement accuracy or prove fraudulent intent. No operating threshold is tuned using the labels during this run.
