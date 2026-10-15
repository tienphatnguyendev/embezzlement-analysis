# Evaluation and research backlog

## Current evidence

Unit tests verify implementation behavior. The authored demo verifies end-to-end reporting. The publisher prefix verifies format compatibility. None measures embezzlement-detection accuracy. No model has been trained and no full HI-Small benchmark has been run.

## Next experiment

1. Define the authorized scope, available accounts, statement date coverage, and reviewer decision criteria. Record a reason to investigate and revisit it as evidence changes.
2. Acquire a complete version of HI-Small and record its hash. Keep its AML label namespace separate from independently established embezzlement case labels. Inspect the publisher's all-laundering tail artifact.
3. Integrate account identities and evidence-backed vendor/employee context. Implement the deferred ACFE tests in the methodology matrix, beginning with shared vendor/employee account identifiers and invoice support.
4. Build a separate scenario dataset with approved payments, supplier payroll, refunds, intercompany transfers, missing records, and split/merged flows. Add suspected embezzlement scenarios with case IDs and independently documented outcomes. Keep those labels separate from input features.
5. Compare a baseline using individual transaction features with the path/context rules. Split chronologically and keep case-connected transfers from leaking across partitions. If these requirements conflict at a cutoff, exclude the crossing case or assign the whole case to a later evaluation window and document the choice. Use only information available at each decision time.
6. Measure precision (the share of flagged cases the reviewer confirms), recall (the share of known cases found), and precision among the top K reviewed leads. Report reviewed/unreviewed cases separately; an unreviewed case is not a negative example. Record coverage, false-positive reasons, latency, and truncated searches. The current engine has no ranking, so define and validate a ranking before reporting top-K performance.

## Required next data and code

| Work item | Additional evidence | Deliverable |
| --- | --- | --- |
| Vendor/employee comparisons | Approved master-data exports with stable IDs and effective dates | Exact-ID matching with explainable conflict leads |
| Invoice validation | Invoice, purchase order, goods/service receipt, authorization records | Missing/duplicate/mismatched support checks |
| Statement parsing | Authorized PDFs/exports and bank-specific layout samples | Extraction with page/row provenance and reconciliation |
| Multi-account reconciliation | Statement references and transfer identifiers | Link mirrored entries without erasing repeated payments |
| Split/merged transfers | Complete windows and balance information | Explicit, reviewed allocation assumptions; no double-counted totals |
| Investigation interface | Reviewer needs and access model | Case review with corroborating and contrary evidence |

## Decision boundary

An observed path and an employment relationship support a question to investigate. They do not establish fraudulent intent, lack of authorization, a sham vendor, or the amount of a loss. Preserve contradictory evidence and uncertainty. A shell company may have a lawful purpose. Evaluate the methods against each intended deployment context before using them on real cases.
