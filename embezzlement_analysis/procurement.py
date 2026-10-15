"""Review supplied invoice, purchase-order, receipt, and approval evidence.

Findings identify record inconsistencies and evidence gaps, never fraud or
loss. Invoice totals describe supplied records, not confirmed payments.
"""

from collections import defaultdict
from fractions import Fraction

from .evidence import load_table
from .numeric import positive_bounded_decimal


INVOICES = ['invoice_id', 'vendor_id', 'invoice_number', 'po_id', 'amount',
            'currency', 'invoice_approved_by', 'payment_approved_by', 'evidence_ref']
POS = ['po_id', 'vendor_id', 'amount', 'currency', 'requested_by', 'approved_by', 'evidence_ref']
RECEIPTS = ['receipt_id', 'po_id', 'vendor_id', 'amount', 'currency', 'evidence_ref']


def _amount_string(value):
    """Serialize a nonnegative Fraction with a finite decimal expansion exactly."""
    whole, remainder = divmod(value.numerator, value.denominator)
    if not remainder:
        return str(whole)
    fractional = []
    while remainder:
        digit, remainder = divmod(remainder * 10, value.denominator)
        fractional.append(str(digit))
    return str(whole) + '.' + ''.join(fractional)


def _validate(rows, key, table):
    """Reject ambiguous identities before analysis; retain identifier strings."""
    by_id = {}
    for row in rows:
        for field in [key, 'vendor_id', 'currency', 'evidence_ref']:
            if not row[field].strip():
                raise ValueError('{} CSV record {}: {} cannot be empty'.format(
                    table, row['_source_row'], field))
        identifier = row[key]
        if identifier in by_id:
            raise ValueError('{}: duplicate {} {!r}'.format(table, key, identifier))
        row['_amount'] = Fraction(positive_bounded_decimal(row['amount'], table + '.amount'))
        by_id[identifier] = row
    return by_id


def analyze_procurement(invoices_path, purchase_orders_path, receipts_path, max_findings=1000):
    """Check supplied evidence using exact, currency-specific grouped amounts.

    Amounts use the shared finite positive decimal limits: <=38 coefficient
    digits, stored exponent >=-18, magnitude <1e38. Fraction sums avoid rounding
    under Decimal's default arithmetic context. Only invoices and receipts
    matching a PO's vendor and currency enter its comparable totals. Multiple
    receipts may document split deliveries; multiple invoices may bill one PO.
    The report does not allocate deliveries to individual invoices or infer
    payment, authorization, guilt, or loss. All rows are validated even when
    the finding limit is reached; only max_findings findings are retained.
    """
    if isinstance(max_findings, bool) or not isinstance(max_findings, int) or max_findings < 1:
        raise ValueError('max_findings must be a positive integer')
    invoices, invoice_source = load_table(invoices_path, INVOICES)
    pos, po_source = load_table(purchase_orders_path, POS)
    receipts, receipt_source = load_table(receipts_path, RECEIPTS)
    _validate(invoices, 'invoice_id', 'invoices')
    po_by_id = _validate(pos, 'po_id', 'purchase_orders')
    _validate(receipts, 'receipt_id', 'receipts')
    sources = {'invoices': invoice_source, 'purchase_orders': po_source, 'receipts': receipt_source}
    result = {'sources': sources, 'findings': [], 'truncated': False, 'limitations': [
        'These findings are review leads, not conclusions of fraud, unauthorized payment, or loss.',
        'Missing records mean missing supplied evidence; underlying documents may exist elsewhere.',
        'Invoice amounts describe supplied invoice records, not confirmed bank payments. Duplicate '
        'invoice references may be repeated records or reused numbers and require reconciliation.',
        'Totals include only records matching the purchase order vendor and currency; no exchange '
        'rates or cross-currency conversions are inferred.',
        'Receipt amounts represent supplied monetary delivery or acceptance evidence. Many invoices '
        'and receipts can relate to one PO; this check does not allocate receipts to invoices.',
        'Approval names describe supplied records. Role overlap requires review of policy, authority, '
        'and any permitted exceptions; missing names do not prove approval never occurred.',
        'The files contain no dates, approved change orders, credit notes, tax breakdown, or '
        'organization-specific approval thresholds. Split-order and timing tests are not performed.',
    ]}
    id_fields = {'invoices': 'invoice_id', 'purchase_orders': 'po_id', 'receipts': 'receipt_id'}

    def reference(table, row):
        return {'table': table, 'record_id': row[id_fields[table]],
                'source_sha256': sources[table]['sha256'], 'source_row': row['_source_row'],
                'evidence_ref': row['evidence_ref']}

    def emit(rule, summary, records, details):
        if len(result['findings']) >= max_findings:
            result['truncated'] = True
            return
        result['findings'].append({'rule_id': rule, 'summary': summary,
                                   'vendor_id': details.get('vendor_id'), 'details': details,
                                   'references': [reference(table, row) for table, row in records]})

    invoice_groups = defaultdict(list)
    receipt_groups = defaultdict(list)
    number_groups = defaultdict(list)
    duplicate_invoice_ids = set()
    for invoice in invoices:
        if invoice['invoice_number'].strip():
            number_groups[(invoice['vendor_id'], invoice['invoice_number'])].append(invoice)
    for (vendor_id, number), group in number_groups.items():
        if len(group) > 1:
            duplicate_invoice_ids.update(row['invoice_id'] for row in group)
            emit('duplicate_invoice_reference',
                 'Multiple supplied invoice records share a vendor and invoice number; '
                 'this is not proof of duplicate payment.',
                 [('invoices', row) for row in group],
                 {'vendor_id': vendor_id, 'invoice_number': number, 'record_count': len(group)})

    for po in pos:
        detail = {'vendor_id': po['vendor_id'], 'po_id': po['po_id']}
        missing = [field for field in ['requested_by', 'approved_by'] if not po[field].strip()]
        if missing:
            emit('missing_po_approval', 'Purchase-order requester or approver is missing in supplied evidence.',
                 [('purchase_orders', po)], dict(detail, missing_fields=missing))
        if po['requested_by'].strip() and po['requested_by'] == po['approved_by']:
            emit('po_approval_overlap', 'The supplied PO requester and approver identifiers are identical.',
                 [('purchase_orders', po)], dict(detail, approver=po['approved_by']))

    for invoice in invoices:
        detail = {'vendor_id': invoice['vendor_id'], 'invoice_id': invoice['invoice_id'],
                  'po_id': invoice['po_id']}
        records = [('invoices', invoice)]
        if not invoice['invoice_number'].strip():
            emit('missing_invoice_number', 'Invoice number is missing in supplied evidence.', records, detail)
        missing = [field for field in ['invoice_approved_by', 'payment_approved_by']
                   if not invoice[field].strip()]
        if missing:
            emit('missing_invoice_approval', 'Invoice or payment approver is missing in supplied evidence.',
                 records, dict(detail, missing_fields=missing))
        if (invoice['invoice_approved_by'].strip()
                and invoice['invoice_approved_by'] == invoice['payment_approved_by']):
            emit('invoice_approval_overlap', 'The supplied invoice and payment approver identifiers are identical.',
                 records, dict(detail, approver=invoice['invoice_approved_by']))
        if not invoice['po_id'].strip():
            emit('missing_po_reference', 'Invoice has no purchase-order reference in supplied evidence.', records, detail)
            continue
        po = po_by_id.get(invoice['po_id'])
        if po is None:
            emit('po_not_found', 'Referenced purchase order is not present in the supplied PO file.', records, detail)
            continue
        if po['approved_by'].strip() and po['approved_by'] == invoice['payment_approved_by']:
            emit('purchase_payment_approval_overlap',
                 'The supplied purchase-order and payment approver identifiers are identical.',
                 records + [('purchase_orders', po)], dict(detail, approver=po['approved_by']))
        mismatches = [field for field in ['vendor_id', 'currency'] if invoice[field] != po[field]]
        if mismatches:
            emit('invoice_po_mismatch', 'Invoice vendor or currency differs from its referenced PO; '
                 'this invoice is excluded from comparable totals.', records + [('purchase_orders', po)],
                 dict(detail, mismatched_fields=mismatches, invoice_currency=invoice['currency'],
                      po_currency=po['currency'], po_vendor_id=po['vendor_id']))
            continue
        invoice_groups[po['po_id']].append(invoice)

    for receipt in receipts:
        detail = {'vendor_id': receipt['vendor_id'], 'receipt_id': receipt['receipt_id'],
                  'po_id': receipt['po_id']}
        records = [('receipts', receipt)]
        if not receipt['po_id'].strip():
            emit('receipt_missing_po_reference', 'Receipt has no purchase-order reference in supplied evidence.', records, detail)
            continue
        po = po_by_id.get(receipt['po_id'])
        if po is None:
            emit('receipt_po_not_found', 'Receipt references a PO absent from the supplied PO file.', records, detail)
            continue
        mismatches = [field for field in ['vendor_id', 'currency'] if receipt[field] != po[field]]
        if mismatches:
            emit('receipt_po_mismatch', 'Receipt vendor or currency differs from its referenced PO; '
                 'this receipt is excluded from comparable totals.', records + [('purchase_orders', po)],
                 dict(detail, mismatched_fields=mismatches, receipt_currency=receipt['currency'],
                      po_currency=po['currency'], po_vendor_id=po['vendor_id']))
            continue
        receipt_groups[po['po_id']].append(receipt)

    for po_id, group in invoice_groups.items():
        po = po_by_id[po_id]
        billed = sum((row['_amount'] for row in group), Fraction(0))
        comparable_receipts = receipt_groups[po_id]
        received = sum((row['_amount'] for row in comparable_receipts), Fraction(0))
        detail = {'vendor_id': po['vendor_id'], 'po_id': po_id, 'currency': po['currency'],
                  'invoice_total': _amount_string(billed), 'po_authorized': po['amount'],
                  'invoice_count': len(group),
                  'duplicate_invoice_reference_present': any(
                      row['invoice_id'] in duplicate_invoice_ids for row in group)}
        records = [('purchase_orders', po)] + [('invoices', row) for row in group]
        if billed > po['_amount']:
            emit('po_overbilled', 'Combined comparable invoice records exceed the supplied PO amount; '
                 'reconcile duplicates and any approved changes.', records, detail)
        if not comparable_receipts:
            emit('missing_receipt_evidence', 'No matching receipt evidence was supplied for this PO invoice group.',
                 records, dict(detail, receipt_count=0))
        elif billed > received:
            emit('billed_exceeds_receipts', 'Combined comparable invoice records exceed matching supplied receipt '
                 'amounts for the PO; individual invoice allocation is unknown.',
                 records + [('receipts', row) for row in comparable_receipts],
                 dict(detail, receipt_total=_amount_string(received), receipt_count=len(comparable_receipts)))
    return result
