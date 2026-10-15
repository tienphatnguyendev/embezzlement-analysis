# Investigation checks completion plan

The user requested completion as quickly as practical using parallel agents. This iteration completes the documented vendor/employee and invoice checks and adds the missing IBM account adapter. Existing path tracing remains available.

## Contracts

All evidence CSVs have exact headers, retain identifier strings, reject ambiguous keys, and carry a SHA-256 from the exact bytes parsed plus CSV record references. `evidence.load_table(path, fields)` returns `(rows, source)`; rows include `_source_row`, source has `file_name`, `sha256`, `row_count`. A file is limited to 64 MiB. No runtime dependencies are added.

1. `masters.analyze_masters(vendors_path, employees_path, max_findings=1000)` returns JSON-safe `{sources,findings,truncated,limitations}`. Index fields to avoid full pairwise scans. Nonempty account, tax ID, address and name matches remain review signals, with exact matched values and references. Name-only matches are weak. Never assert employment from an account match.
2. `procurement.analyze_procurement(invoices_path, purchase_orders_path, receipts_path, max_findings=1000)` returns the same shape. Check duplicate vendor/invoice numbers, missing/mismatched PO and receipt evidence, aggregate invoicing above a PO's authorized amount, and missing or overlapping approvers. Require currency/vendor continuity. Many-to-one billing is handled explicitly; no automatic fraud or loss decision.
3. `accounts.load_ibm_accounts(path)` returns `(context,source)` in the existing context format. Classify synthetic names only as derived business/person/unknown. Preserve source-row references, normalize only numeric bank IDs, reject duplicates/conflicts, and never invent employee links. CLI `trace --ibm-accounts` can be combined with explicit `--context`; reject overlapping contradictory identities, while allowing explicit employment enrichment.
4. Add `check-masters`, `check-invoices`, and combined `investigate` CLI commands. The combined report includes existing paths plus both evidence checks when all required inputs are supplied. Preserve source manifests and report incompleteness in each section. Test real subprocess flows.
5. Add authored benign and concerning fixtures, schema documentation, evidence gaps, then cross-review each module and run whole-repository tests and demos.

## Scope and interpretation

Complete means the above local analysis functions work together. Bank-specific OCR, trained classifiers, split/merged fund allocation and a production web interface require additional source material and remain separate work. Absent records are reported as missing supplied evidence rather than proof an underlying document never existed. Records have no effective-date fields, so relationship matches describe the supplied snapshot rather than historical ownership.

## Progress

- Planning: complete; three independent implementers assigned, parent owns shared evidence reader and CLI.
- Vendor/employee checks: complete; 15 targeted tests and independent procurement-agent review.
- Invoice/approval checks: complete; 16 targeted tests, cross-review correction and scoped re-review.
- IBM account adapter: complete; 15 targeted tests and CLI integration.
- Combined report and shared evidence handling: complete; provenance, bounded links, saved counts and cross-module subprocess tests.
- Repository validation: 103 tests pass; authored investigation runs end to end. Source/method documentation reflects implemented behavior.
