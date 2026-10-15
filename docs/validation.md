# Validation record

Date: 2026-10-15. Environment: macOS, Python 3.9.6, standard-library SQLite.

- `python3 -m unittest discover -s tests -q`: 103 tests passed after version 0.2 integration (initial baseline: 47).
- `python3 -m compileall -q embezzlement_analysis`: passed.
- Editable package build/install and installed `embezzlement-analysis --help`: passed in `.venv`. The system's old pip did not support this editable build; the documented setup now upgrades pip inside the virtual environment first.
- Authored demo: 8 imported transaction records, 3 candidate paths, no truncation. Two overlapping paths carry the explicitly supplied employee relationship; the supplier-payroll lookalike remains a candidate without that relationship.
- Publisher data: imported 10,701 records from the bounded HI-Small prefix, with hash and row counts verified. This is not a full dataset benchmark.
- Traced the three most active origin accounts in that prefix with default filters: zero candidates, no truncation. That result says nothing about fraud prevalence or recall because the prefix omits most of the network.
- Independent code review found four issues: identity whitespace normalization, invalid CLI numeric arguments, context fingerprint consistency, and numeric conversion resource bounds. Added regression tests, fixed all four, and obtained a clean focused re-review.
- Version 0.2 cross-review identified missing purchase/payment approver comparison and an incomplete saved-report count. Both now have regression coverage and clean scoped re-review. Master matching and IBM context integration received independent review without remaining material findings.
- Complete authored investigation: 3 path candidates, 2 master matches, 7 invoice/approval exceptions and 5 vendor/path links, with no truncation. These are overlapping review outputs, not independent confirmed incidents. The benign supplier remains free of procurement and employee-overlap findings.

No fraud-accuracy, loss-recovery, or production-readiness claim is made. Future validation is specified in [evaluation.md](evaluation.md).
