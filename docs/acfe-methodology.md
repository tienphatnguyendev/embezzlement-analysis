# ACFE-informed methodology and implementation boundary

Research accessed: **2026-10-15**. This document uses primary ACFE resources and articles published by ACFE's Fraud Magazine. It distinguishes their guidance from this repository's engineering choices. ACFE has not certified or endorsed this software.

## Purpose and v0 boundary

v0 finds **candidate transaction paths** from a selected business account, through an intermediate account, to a destination account. Optional, evidence-backed account context can describe business/personal roles and employee relationships. A candidate means that records meet the configured selection rules; it does not establish theft, a fictitious vendor, ownership, intent, or guilt.

Invoice analysis, vendor-master comparisons, purchasing controls and proof-of-delivery tests are future work. A bank transfer alone cannot establish that an invoice was false or that a vendor supplied nothing. Account context supplied by an analyst remains an attributed assertion until its supporting evidence is checked.

## Verified source register

All entries below were accessed on **2026-10-15**. Source summaries paraphrase the published material; they are not quotations. An article's case examples describe its authors' experience and should not become universal detection rules.

### ACFE-01 — Shell Companies

- Publisher: ACFE.
- URL: <https://www.acfe.com/fraud-resources/shell-companies>
- Relevant sections: “What is a shell company?” and “Investigating shell companies.”
- Supported guidance: Shells can serve lawful or unlawful purposes. Investigators examine public business records and listed people, then map relationships. Missing online presence is inconclusive; registry entries can fail to reveal the ultimate owner. Financial documents may be necessary to understand the money trail.

### ACFE-02 — Anti-Fraud Data Analytics Tests

- Publisher: ACFE.
- URL: <https://www.acfe.com/fraud-resources/fraud-risk-tools---coso/anti-fraud-data-analytics-tests>
- Relevant sections: Purchasing Schemes, Billing Schemes, Bid Rigging and Check Tampering.
- Supported guidance: Compare employee and vendor identifiers, addresses and account details. Examine incomplete vendor records, duplicate invoices, invoice sequences, expedited purchases and failed purchase-order/receipt/invoice matching. Compare purchase and payment approvers. Investigate split contracts relative to actual approval limits. These tests identify red flags requiring examination.

### ACFE-03 — Audit Those Vendors

- Publisher: Fraud Magazine / ACFE; Craig L. Greene, CFE, CPA; May 1, 2003.
- URL: <https://www.acfe.com/fraud-magazine/all-issues/issue/article?s=2003-mayjune-auditing-vendors>
- Supported guidance: Vendor audits examine overbilling and whether goods or services were delivered. The article describes shell intermediaries that add markups or bill for nonexistent deliveries. Payment records, supporting operational documents and ownership records help test the explanation. Its opening case detects overlapping labor charges across divisions.
- Access note: The current article page exposes a preview; additional text was available in the search tool's indexed ACFE result. This document does not reproduce the article.

### ACFE-04 — Global Risks Reduced: International Business Doesn’t Have to Be Risky

- Publisher: Fraud Magazine / ACFE; Mona Clayton, CFE, CPA; March 1, 2000.
- URL: <https://www.acfe.com/fraud-magazine/all-issues/issue/article?s=2000-marapr-reducing-international-business-risks>
- Relevant sections: “Examining the Cash Flow” and vendor-payment procedures.
- Supported guidance: Trace transfers against bank records and accounting entries. A reconciled balance alone can conceal misleading journal entries. Compare actual payees and cleared payments with recorded disbursements, including wires maintained outside the check register. Compare vendor and employee addresses and examine unexplained vendor-payment changes.

### ACFE-05 — Predication or not?

- Publisher: Fraud Magazine / ACFE; Dick Carozza, CFE; November 1, 2020.
- URL: <https://www.acfe.com/fraud-magazine/all-issues/issue/article?s=2020-novdec-predication-fraud-examination>
- Supported guidance: Predication means a reasonable factual basis for an investigation. Examiners consider the circumstances and reassess that basis and their scope as evidence develops. The article discusses combining transactional anomalies, controls, tips and other information instead of relying on one symptom.
- Access note: The current article page exposes a preview; indexed ACFE text also supported this summary.

### ACFE-06 — CFE CODE OF PROFESSIONAL STANDARDS: INTERPRETATION AND GUIDANCE

- Publisher: ACFE; publicly accessible PDF.
- URL: <https://www.acfe.com/about-the-acfe/-/media/9560BECA7A1441B5B3CD9A6E14CE7B89.ashx>
- Relevant sections: III.C, IV and V; printed pages 10, 18 and 21–23.
- Supported guidance: Support conclusions with relevant, reliable and sufficient evidence. Consider evidence pointing both toward and away from an allegation. Reports must avoid misleading presentation and opinions about guilt or innocence. The predication requirement for investigatory examinations does not prohibit ordinary risk assessment without an existing allegation.

### ACFE-07 — Remote but engaged

- Publisher: Fraud Magazine / ACFE; Dick Carozza, CFE; January 1, 2021.
- URL: <https://www.acfe.com/fraud-magazine/all-issues/issue/article?s=2021-janfeb-remote-but-engaged>
- Relevant section: “Chain of custody.”
- Supported guidance: Chain of custody means the documented history of who possessed evidence and what they did with it. Record collection details, people, dates, document identifiers, access and storage arrangements so later users can assess whether evidence changed.

## Methods, required data and implementation mapping

The designs in the last column are **our engineering interpretations**, not prescribed ACFE algorithms. “Future” means the v0 implementation does not perform that test.

| Method and source | Required data | Repository application |
| --- | --- | --- |
| Examine cash movements (ACFE-04) | Directed transactions with unique IDs, both account IDs, timestamps, amount, currency and source references | **v0:** enumerate observable account-to-account paths; expose each leg and its time/amount comparison. Report missing downstream coverage. |
| Investigate account/entity relationships (ACFE-01) | Account/entity mappings, relationship type, source evidence and effective dates where known | **v0 optional context:** attach sourced roles. Preserve unknowns; do not infer personal ownership from an account name or classify a business as fraudulent. |
| Employee/vendor connections (ACFE-02) | Employee and vendor identifiers plus banking/ownership evidence | **v0 optional context:** attach explicit documented employee links. **Future:** compare full master files, preserving match fields and ambiguity for review. |
| Test procurement/payment consistency (ACFE-02) | Invoice header/lines, purchase orders, receipts, payment allocation, approval events and company limits | **Future:** duplicate groups, three-way-match exceptions and split-order candidates. Use organization-specific limits; distinguish repeated invoice lines, credits and legitimate instalments. |
| Test delivery and price rationale (ACFE-03) | Contract terms, delivery receipts, time records, item quantities/rates and invoices | **Future:** compare billed work and prices against documented delivery and contractual expectations. Bank-only inputs cannot run this test. |
| Reassess investigative basis (ACFE-05) | Allegation, scope, source coverage and competing explanations | **Design:** keep the analyst's case rationale distinct from automated candidate criteria. A positive match does not automatically establish predication. |
| Evidence-supported reporting (ACFE-06) | Findings, supporting references, contradictory records and unresolved gaps | **Design:** separate observations from interpretation; record exculpatory evidence (facts that weaken an allegation) alongside supporting evidence. |
| Preserve evidence history (ACFE-07) | Original files, collection metadata, row/page references and handling history | **Design:** preserve originals; use separate normalized data, input hashes and run metadata. A hash detects later byte changes; it cannot authenticate an original record or replace custody documentation. |

## Candidate-path rules: project heuristics

The proposed **72-hour** time window and **0.80–1.05** onward-to-incoming amount ratio are configurable project heuristics: practical filters for selecting paths to review. **They are not ACFE thresholds, validated probabilities, or definitions of fraud.** The ratio compares the later payment amount with the preceding incoming amount; any implementation using a different denominator must state it explicitly in its output.

Time/amount similarity can arise from legitimate cash management, loan repayment, subcontracting or normal vendor settlement. Record actual lags, amounts, ratios and the active configuration so a reviewer can reproduce selection. Use same-currency comparisons unless a separate, documented exchange-rate method exists. State whether timestamps represent posting, booking or value time; a date-only record cannot establish intraday order.

Missing records do not mean that no transaction occurred. “No candidate found” means only that the supplied, accepted records did not meet the selected rules. The absence of employee context does not establish that an employee has no connection. Public ownership records add context; they do not supply missing bank transfers.

## Reporting and attribution limits

An observed transfer proves only what the supplied record documents. A path connects transactions by account, order and configured similarity; it does not prove that the exact same funds financed the next payment. Mixed funds, earlier balances, unobserved deposits, refunds and overlapping candidate paths make that inference unsafe without a separate tracing method.

**v0 performs no loss aggregation and no mixed-funds attribution.** Do not add the amounts of every leg or every overlapping path and call the result stolen funds, loss, proceeds or recovery. Report individual transaction amounts and candidate counts. Leave financial attribution unresolved.

A review should preserve reasonable alternative explanations, conflicting account mappings, documented legitimate services and repayments. Label outcomes as candidates or observations. “Shell company,” “employee-linked account” and “personal account” require their own evidence; none is synonymous with fraud. The software cannot certify a forensic conclusion or establish guilt.
