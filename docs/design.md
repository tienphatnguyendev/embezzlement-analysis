# Embezzlement analysis research baseline

Date: 2026-10-15. Scope: local research and investigator support using synthetic data.

## Intent and assumptions

Investigate the hypothesis company → intermediary → personal account. The user requested a repository grounded in ACFE methods and IBM's AMLworld paper. Start with a Python command-line tool, SQLite, and standard-library tests. No service or credentials are needed. A local Git repository is the deliverable; remote hosting can follow separately.

## Approach

A reproducible command-line pipeline makes input validation and evidence references easy to test. A notebook would help exploration but makes repeatable imports harder; a web application adds infrastructure before the analysis is validated. This first version therefore uses the CLI.

Import IBM-format CSV into SQLite transactionally. Identify accounts by the pair (bank, account), preserve account strings and exact decimal amounts, and record the source file SHA-256 digest and CSV record number. A digest is a fingerprint of file contents. Re-importing identical bytes does not duplicate records. Identical-looking rows within one source remain separate payments. Labels are retained only for later evaluation.

Search from an explicitly selected account for simple paths of 2–3 payments by default. Each later payment must have a strictly later timestamp, fall within a configurable total window, and pay in the currency received at the preceding hop. Compare the next paid amount to the previous received amount with configurable bounds. These are engineering heuristics, not ACFE thresholds or an allocation of particular funds. Keep each payment and both currency amounts in the result. Do not aggregate paths into a loss total.

Optional account context supplies entity type, entity identifier, employment relationship, and evidence reference. Unknown context remains unknown. A company-to-person path and employee link can strengthen a review lead; neither establishes a sham company or theft. Synthetic fixtures include both a concerning scenario and a legitimate supplier-payroll lookalike.

## Outputs and boundaries

JSON reports contain parameters, source digests, source-row references, candidate paths, evidence gaps, and explicit truncation indicators. A checked-in demo is authored for this project and must never be described as an IBM sample. A separately fetched IBM prefix is only an ingestion smoke test, not a representative benchmark.

Bound search work and path count to prevent uncontrolled expansion. Reject malformed input atomically. Do not infer personal-account status from account names. No OCR, invoice detector, beneficial-ownership inference, automated guilt decision, fund allocation, or production model is included in v0.

## Validation

Test duplicate headers, account collisions across banks, leading zeros, invalid/negative/non-finite amounts, bad timestamps, rollback, repeat import, label independence, time ordering, currency continuity, path bounds, cycles, incomplete visibility, context conflicts, and benign lookalikes. Verify the documented CLI end to end, plus a small publisher-sourced sample when available.
