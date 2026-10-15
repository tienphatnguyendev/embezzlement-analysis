# Implementation plan

Goal: deliver a runnable, source-grounded research baseline, with transparent limits.

Stack: Python 3.9+, SQLite, argparse, Decimal, unittest. Spec: [design.md](design.md).

1. Implement and test `ingest.py`: strict positional IBM CSV import, source hashes, indexed transaction storage, atomic validation, and safe repeated imports.
2. Implement and test `analysis.py`: bounded time-ordered path search, currency-aware amount comparisons, no use of labels in candidate selection.
3. Implement and test `context.py` and `__main__.py`: evidence-backed entity annotations, CLI imports/tracing, JSON reports, explicit error handling.
4. Add authored fixtures, ACFE method-to-data mapping, IBM data card, dataset acquisition instructions, and evaluation roadmap.
5. Run all tests, demo and publisher-sample ingestion; request independent code review; resolve material findings and commit locally.

Review focus: no bank/account key collisions; no invented roles from IBM labels; no currency-mismatched comparisons; no silent partial imports or search truncation; no claims of tracing the same funds through mixed balances.
