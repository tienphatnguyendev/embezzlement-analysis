# IBM AMLworld data card

Verified: 2026-10-15. The user's specified source is [Realistic Synthetic Financial Transactions for Anti-Money Laundering Models, v3](https://arxiv.org/html/2306.16424v3).

## What the paper supports

Section 3.3 lists embezzlement among nine simulated sources of illicit income. Section 3.4 models people, companies, accounts, and ordinary economic activity. Released labels distinguish laundering from other transactions; they do not identify a particular embezzlement case. Account graphs support investigation of connected transfers, but cannot establish employment, authorization, or a fictitious business purpose. Section 3.1 discusses limited visibility across banks. Section 4 describes temporal evaluation; future transactions must not inform a prediction about an earlier event. These points motivate our research design, not a claim of real-world detection performance.

## Publisher and files

- [IBM AML-Data repository](https://github.com/IBM/AML-Data): data license **CDLA-Sharing-1.0**; repository code has a different license.
- [Kaggle dataset page](https://www.kaggle.com/datasets/ealtman2019/ibm-transactions-for-anti-money-laundering-aml).
- [HI-Small transactions](https://www.kaggle.com/api/v1/datasets/download/ealtman2019/ibm-transactions-for-anti-money-laundering-aml/HI-Small_Trans.csv): verified raw CSV download, 475,664,283 bytes.
- [HI-Small accounts](https://www.kaggle.com/api/v1/datasets/download/ealtman2019/ibm-transactions-for-anti-money-laundering-aml/HI-Small_accounts.csv): verified file, 34,053,187 bytes.
- [HI-Small patterns](https://www.kaggle.com/api/v1/datasets/download/ealtman2019/ibm-transactions-for-anti-money-laundering-aml/HI-Small_Patterns.txt): separate laundering-attempt blocks for future evaluation.

These endpoints worked without credentials during verification. Access behavior may change. Downloaded records remain outside Git.

## Transaction contract

```text
Timestamp,From Bank,Account,To Bank,Account,Amount Received,Receiving Currency,Amount Paid,Payment Currency,Payment Format,Is Laundering
```

The importer validates this exact header and reads by position so duplicate headings cannot discard an account. Timestamps use `YYYY/MM/DD HH:MM` and specify no timezone. Files are not necessarily time-sorted. Amounts remain positive, finite decimal values; both paid and received currency are retained. The numeric safety limits are documented in the numeric validation module.

Use `(normalized bank ID, exact account number)` as the account identity. For example, transaction bank `001` matches account-file bank `1`. Never turn account numbers into integers. This approach is consistent with the bank/account distinction in [IBM's reference preprocessing](https://github.com/IBM/Multi-GNN/blob/main/format_kaggle_files.py).

The accounts file has `Bank Name,Bank ID,Account Number,Entity ID,Entity Name`. Any type inferred from a synthetic entity name is a derived classification. The file does not provide employment links, invoice records, ownership edges, or confirmed shell labels. Version 0.2 integrates this file through `--ibm-accounts`, retaining derived-classification provenance and rejecting contradictory explicit context.

No global transaction identifier is supplied. We retain `(source SHA-256, CSV record number)` and preserve repeated rows. That identifies evidence within an export; it cannot deduplicate overlapping exports or mirrored entries across bank statements.

## Acquired prefix

The workspace acquisition requested bytes `0–1048575` and required HTTP 206 (partial content). It removed the incomplete final CSV line and saved 1,048,527 bytes / 10,701 transaction records. SHA-256:

```text
d9c5a0ce179fd460f4cae06368db9f1e08beeea9369736a180e116b7a424374f
```

This prefix is an ingestion smoke test. It is not random, representative, or a valid test set for embezzlement detection. The manifest records origin, range, retrieval date, and digest. The authored demo is an entirely separate fixture.

## Leakage and evaluation

The [publisher's dataset description](https://www.kaggle.com/api/v1/datasets/view/ealtman2019/ibm-transactions-for-anti-money-laundering-aml) warns that the tail after the main activity period contains only laundering transactions. Audit this artifact before modeling. Keep laundering labels and pattern-file membership out of detector features; keep connected case records together during evaluation. Compare outcomes on full authorized windows and document data coverage. Synthetic AML results cannot be reported as confirmed embezzlement accuracy.

The full version-8 audit performed on 2026-10-15 contradicts the literal all-laundering claim: September 11–18 contains 1,108 transactions, with 655 label-1 and 453 label-0 rows. The tail remains strongly enriched. The complete ledger contains 5,078,345 transactions and 5,177 label-1 rows; all endpoints join to metadata. [Full run method](full-hi-small-method.md) and the local `reports/hi-small-findings.md` document the measured results.
