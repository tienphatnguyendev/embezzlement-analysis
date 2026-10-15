# Full HI-Small result, 2026-10-15

**The current hypothesis did not identify any laundering-labeled transactions.** It selected 905 two-payment business → business → person chains, involving 448 distinct transactions, all labeled 0. This is a poor result for the current rule on this snapshot, not evidence that the ledger contains no laundering or embezzlement.

The run downloaded complete publisher version-8 transaction, account and pattern files; independently audited their bytes and records; imported all 5,078,345 transactions; validated SQLite with quick-check; and scanned the full ledger with no candidate cap. The source has 5,177 laundering-labeled rows, 515,088 observed bank/account identities, and 518,581 metadata accounts. Every endpoint joined to metadata. No source rows were rejected by the importer.

The fixed rule uses distinct accounts/entities, increasing timestamps, at most 72 hours, adjacent currency continuity, and an exact onward-paid/incoming-received ratio of 0.80–1.05. Roles derive from synthetic name prefixes. Labels and pattern membership are accessed only after selection and do not rank examples. The scan examined 19,577 time/currency/role-compatible pairs, rejected 18,645 by ratio, and excluded 27 amount-compatible repeated-owner/account pairs. All 905 remaining chains are in the main activity window. Their first/second edge sets contain 355/93 transactions, with 448 in their union.

Important limitations:

- Only 740 metadata accounts have an explicit Individual prefix; 6,759 have unknown roles. This limits the target shape represented by the role filter.
- All 370 annotated laundering attempts lack person-classified accounts. Their 3,209 rows therefore cannot instantiate our specified person-ending hypothesis within those attempts. They cover only part of the 5,177 laundering-labeled transactions.
- The publisher describes later rows as all laundering. Actual September 11–18 rows contain 655 label 1 and 453 label 0, out of 1,108 total. Treat the tail separately; do not assume the description is literal for this snapshot.
- IBM supplies no employee/vendor masters, invoices, delivery records, approvals, confirmed shell status or embezzlement case labels. Those ACFE checks were not run because their evidence is absent. Authored examples were not mixed into the full dataset.
- The scan covers a specified two-payment rule, not longer/split/merged chains. It does not allocate funds or quantify loss. Synthetic laundering labels are not confirmed embezzlement outcomes.

Measured runtime: import 483.04 seconds; exhaustive scan 72.29 seconds. These are observations on this machine, not performance guarantees. The independent audit and SQLite counts agree. All 119 repository tests pass.

Local generated artifacts are ignored by Git: `reports/hi-small-findings.md`, `reports/hi-small-scan.json`, `reports/hi-small-candidates.jsonl`, `reports/hi-small-audit.json`, `reports/hi-small-pattern-scope.json`, and `data/raw/full-hi-small/acquisition.json`. The human-readable findings include examples, input/output hashes, parameter values, coverage and commands. [Run method](full-hi-small-method.md) describes the reproducible scope. Data remains under the publisher's CDLA-Sharing-1.0 terms.
