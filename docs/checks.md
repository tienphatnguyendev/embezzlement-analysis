# Investigation commands and input contracts

Version 0.2 completes the initial vendor/employee, invoice-support, and approval checks. All outputs identify review leads and supplied-evidence gaps. Source hashes identify the exact CSV bytes parsed; references use CSV record numbers including the header as record 1.

## Run the complete authored example

```sh
python3 -m embezzlement_analysis ingest examples/demo_transactions.csv --db data/demo.sqlite
python3 -m embezzlement_analysis investigate --db data/demo.sqlite --bank 1 --account VICTIM --ibm-accounts examples/ibm_accounts.csv --context examples/demo_context.csv --vendors examples/vendors.csv --employees examples/employees.csv --invoices examples/invoices.csv --purchase-orders examples/purchase_orders.csv --receipts examples/receipts.csv --output reports/investigation.json
```

Output paths must be new. Omit `--output` to print the complete report. Run `--help` on any command for options.

Independent checks do not require a transaction database:

```sh
python3 -m embezzlement_analysis check-masters --vendors examples/vendors.csv --employees examples/employees.csv
python3 -m embezzlement_analysis check-invoices --invoices examples/invoices.csv --purchase-orders examples/purchase_orders.csv --receipts examples/receipts.csv
```

## Vendor and employee snapshots

Required headers, in order:

```text
vendor_id,name,bank,account,address,tax_id,evidence_ref
employee_id,employer_entity_id,name,bank,account,address,tax_id,evidence_ref
```

Primary IDs and evidence references must be nonempty; employee records also require an employer entity ID. Bank/account must both be supplied or both blank. Numeric bank IDs are normalized; account and tax identifiers compare exactly. Names and addresses use case-insensitive comparison with repeated whitespace collapsed. Blank values never match. A name-only match is weak. Other matches identify shared comparison values, not confirmed ownership or employment. Missing vendor bank/address/tax data produces a profile-gap finding.

Indexed lookups avoid comparing every vendor to every employee. Results are ordered by source records, not ranked fraud probability. `--max-findings` caps findings; `truncated` states when further findings were omitted. All input rows are validated before findings are produced.

## Purchasing evidence

Required headers:

```text
invoice_id,vendor_id,invoice_number,po_id,amount,currency,invoice_approved_by,payment_approved_by,evidence_ref
po_id,vendor_id,amount,currency,requested_by,approved_by,evidence_ref
receipt_id,po_id,vendor_id,amount,currency,evidence_ref
```

PO means purchase order. A receipt's amount represents the monetary value of supplied delivery or service-acceptance evidence. These are document-level tables, not raw invoice line items. Each table requires unique primary IDs, vendor ID, currency, evidence reference, and a positive amount. Missing invoice numbers, PO references, or approval identifiers become findings where applicable. Credit notes and zero-value records need a separate adapter; they are not silently interpreted as payments.

Checks identify repeated vendor/invoice-number references; absent or incompatible PO/receipt support; aggregate invoicing above authorized PO or receipt amounts; missing approval identifiers; and approver overlaps. Multiple invoices and receipts can relate to one PO. Only the same vendor and currency contribute to comparable totals. Totals remain exact; they describe supplied documents, not payments or losses. Repeated invoice references may indicate duplicate exports and require reconciliation before interpreting aggregate exceptions.

An approval overlap raises a policy-review question, not an automatic control violation. These tables have no approval dates, change orders, credits, tax components or organization-specific thresholds; timing, split-order and approval-limit tests remain outside this contract.

## IBM accounts and combined report

`trace` and `investigate` accept `--ibm-accounts` with the publisher header:

```text
Bank Name,Bank ID,Account Number,Entity ID,Entity Name
```

Known synthetic name prefixes supply a **derived** business/person classification; all other names remain unknown. The adapter does not invent employee links. Explicit context may refine unknown roles and add sourced employment. Conflicting IDs, names or known roles are rejected; merged records preserve both evidence references.

The combined JSON includes `findings` (payment paths), `master_checks`, `invoice_checks`, and `path_vendor_links`. Links match each recipient account against a supplied vendor bank/account, then reference that vendor's master and invoice findings. Indices in links are one-based positions within the corresponding report section. Vendor identity links do not allocate a bank payment to a particular invoice. `truncated` is true if any section or link generation is incomplete; per-section flags and `truncation_reasons` identify the cause.

Evidence tables have a 64 MiB limit per file. Master/approval records describe a supplied snapshot; they do not establish historical relationships or authority on a transaction date. A lack of findings does not establish a lack of fraud.
