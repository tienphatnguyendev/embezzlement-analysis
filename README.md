# Embezzlement analysis

A local research baseline for reviewing **company → intermediary → personal account** hypotheses. Python 3.9+, SQLite, no runtime dependencies. Findings are candidate payment paths, not findings of guilt or quantified losses.

The repository combines an [ACFE methodology review](docs/acfe-methodology.md), the [IBM AMLworld data card](docs/ibm-data-card.md), an importer, bounded path search, vendor/employee comparisons, invoice/approval checks, and source-linked JSON reports. [Complete workflow and schemas](docs/checks.md) · [Design](docs/design.md) · [Completion plan](docs/completion-plan.md).

The [EDA notebook](notebooks/hi_small_eda.ipynb) explores the full ledger, source coverage, temporal artifacts, currency-specific amounts and overlapping candidate paths. Advanced sections add distribution-shift analysis, account/entity network measures, and chronological anomaly ranking. [Notebook setup and execution](notebooks/README.md) · [Methods and review decisions](docs/eda-methods.md).

## Scan the full IBM dataset

Version 0.3 adds a complete two-payment business → business → person scan. It streams every selected chain to JSONL and compares labels only after selection. [Full-run method and limits](docs/full-hi-small-method.md) · [Measured HI-Small results](docs/full-hi-small-results.md).

```sh
python3 -m embezzlement_analysis ingest data/raw/full-hi-small/HI-Small_Trans.csv --db data/hi-small.sqlite
python3 -m embezzlement_analysis scan --db data/hi-small.sqlite --ibm-accounts data/raw/full-hi-small/HI-Small_accounts.csv --candidates reports/hi-small-candidates.jsonl --output reports/hi-small-scan.json
```

This is exhaustive for the stated two-hop rule, with no candidate cap; examples alone are limited. All outputs must be new paths. Full-file acquisition manifests and reports stay outside Git.

## Run the complete investigation

```sh
python3 -m embezzlement_analysis ingest examples/demo_transactions.csv --db data/demo.sqlite
python3 -m embezzlement_analysis investigate --db data/demo.sqlite --bank 1 --account VICTIM --ibm-accounts examples/ibm_accounts.csv --context examples/demo_context.csv --vendors examples/vendors.csv --employees examples/employees.csv --invoices examples/invoices.csv --purchase-orders examples/purchase_orders.csv --receipts examples/receipts.csv
```

This command joins the available review evidence by account and vendor identity. Use `--output reports/investigation.json` to save a new report. Standalone `check-masters` and `check-invoices` commands are also available; see [input contracts](docs/checks.md).

## Run the authored demo

From this repository directory:

```sh
python3 -m unittest discover -s tests -v
python3 -m embezzlement_analysis ingest examples/demo_transactions.csv --db data/demo.sqlite
python3 -m embezzlement_analysis trace --db data/demo.sqlite --bank 1 --account VICTIM --context examples/demo_context.csv
```

The last command prints JSON. Add `--output reports/my-review.json` to save a new report. Existing report files are never overwritten. Reimporting identical source bytes is safe and does not duplicate rows.

Expect **three paths**: two prefixes along the concerning scenario and one ordinary supplier-payroll path. Two paths receive the `recipient_employee_of_origin` context signal. These are authored teaching examples, **not IBM records or model accuracy measurements**. Labels deliberately do not select paths. See [demo notes](examples/README.md).

An optional editable installation exposes `embezzlement-analysis` as a command:

```sh
python3 -m venv .venv
.venv/bin/python -m pip install --upgrade pip
.venv/bin/python -m pip install -e .
```

## Use IBM data

Download the publisher's CSV through the links in the [data card](docs/ibm-data-card.md). Import a full dataset into its own database:

```sh
python3 -m embezzlement_analysis ingest data/raw/HI-Small_Trans.csv --db data/ibm.sqlite
python3 -m embezzlement_analysis trace --db data/ibm.sqlite --bank BANK_ID --account ACCOUNT_ID --max-hops 3 --window-hours 72
```

Replace `BANK_ID` and `ACCOUNT_ID` with an account in that dataset. The tool rejects origins without outgoing records. Imports stream CSV rows, although indexing a full five-million-row file takes longer than the demo. Full-dataset performance has not been benchmarked.

The initial workspace includes a separately downloaded **10,701-row prefix** in ignored `data/raw/HI-Small_prefix.csv`, with its acquisition manifest and `data/ibm-prefix.sqlite`. It verifies ingestion only. This Git repository does not distribute that file; a fresh clone needs its own download. Do not mix the prefix and the full file in one database: overlapping exports have different hashes and are not automatically reconciled.

## What the code does

- Validates IBM's positional CSV schema, including its duplicate `Account` headings. Preserves account strings and raw bank IDs; normalizes numeric bank IDs for joins.
- Stores exact amounts, timestamps, source fingerprints, and record numbers. A failed import rolls back all rows from that file.
- Finds simple paths of 2–3 transfers by default, up to 6 when configured. Each hop must occur later, within the total time window, and meet adjacent amount/currency constraints.
- Compares the next **paid** amount with the previous **received** amount. Default ratio bounds are 0.80–1.05. These adjustable thresholds are project heuristics, not ACFE standards.
- Keeps evaluation labels out of path selection and report transactions. Stops at explicit work or result limits and marks incomplete searches.

Use `python3 -m embezzlement_analysis trace --help` for options. `max_expansions` counts examined rows, including rejected candidates. A cap reached exactly still conservatively marks the report truncated. Results follow deterministic timestamp/row order; they are not ranked probabilities.

## Optional entity evidence

Supply a CSV with exactly these headings:

```csv
bank,account,entity_id,entity_type,entity_name,employee_of,evidence_ref
```

`entity_type` is `business`, `person`, or `unknown`. `employee_of` holds the employer's **entity ID**, not account number. Every supplied record needs an evidence reference. IDs are exact strings; only numeric bank formatting is normalized. Conflicting records are rejected. Unknown accounts remain unknown. Context is hashed from the same bytes that were parsed.

IBM's account file contains entity names and IDs but does not establish employee relationships or shell-company status. Supply it with `--ibm-accounts`; the adapter preserves source references and marks classifications derived from synthetic names. Explicit context can add compatible sourced relationships.

## Interpretation and next steps

An apparent onward payment does not establish that it used the same money. Accounts can mix unrelated funds; paths overlap. Never sum path amounts into a loss total. Equal-minute payments are excluded because IBM does not establish their order. Missing transfers and unknown identities remain evidence gaps.

Version 0.2 includes vendor/employee master comparisons, invoice–purchase-order–receipt checks, and approval-identifier checks. Next, evaluate against independently labeled cases with legitimate lookalikes. [Evaluation plan](docs/evaluation.md) explains what can and cannot be measured now. Bank-specific OCR, split/merge fund allocation, ownership inference and trained classifiers require further work.

Local source data, databases, and generated reports are ignored by Git. Keep a separate evidence-handling process for real cases; file fingerprints alone are not a complete custody record. IBM data remains subject to its publisher's CDLA-Sharing-1.0 terms; documentation references ACFE without claiming ACFE certification or endorsement.
