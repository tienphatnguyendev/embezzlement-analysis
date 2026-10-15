import csv
import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from embezzlement_analysis.procurement import analyze_procurement


INVOICE_FIELDS = ['invoice_id', 'vendor_id', 'invoice_number', 'po_id', 'amount',
                  'currency', 'invoice_approved_by', 'payment_approved_by', 'evidence_ref']
PO_FIELDS = ['po_id', 'vendor_id', 'amount', 'currency', 'requested_by', 'approved_by', 'evidence_ref']
RECEIPT_FIELDS = ['receipt_id', 'po_id', 'vendor_id', 'amount', 'currency', 'evidence_ref']


class ProcurementTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.invoice = ['i1', 'v1', 'INV-1', 'po1', '40', 'USD', 'reviewer', 'payer', 'invoice:1']
        self.po = ['po1', 'v1', '100', 'USD', 'buyer', 'manager', 'po:1']
        self.receipt = ['r1', 'po1', 'v1', '100', 'USD', 'receipt:1']

    def write(self, name, fields, rows):
        path = self.root / name
        with path.open('w', encoding='utf-8', newline='') as file:
            writer = csv.writer(file)
            writer.writerow(fields)
            writer.writerows(rows)
        return path

    def run_check(self, invoices=None, pos=None, receipts=None, **kwargs):
        inputs = (
            self.write('invoices.csv', INVOICE_FIELDS, [self.invoice] if invoices is None else invoices),
            self.write('purchase_orders.csv', PO_FIELDS, [self.po] if pos is None else pos),
            self.write('receipts.csv', RECEIPT_FIELDS, [self.receipt] if receipts is None else receipts),
        )
        return analyze_procurement(*inputs, **kwargs)

    @staticmethod
    def by_rule(result, rule):
        return [finding for finding in result['findings'] if finding['rule_id'] == rule]

    def test_partial_billing_with_split_receipts_is_clean(self):
        second_invoice = ['i2', 'v1', 'INV-2', 'po1', '35', 'USD', 'reviewer', 'payer', 'invoice:2']
        receipts = [['r1', 'po1', 'v1', '25', 'USD', 'receipt:1'],
                    ['r2', 'po1', 'v1', '50', 'USD', 'receipt:2']]
        result = self.run_check(invoices=[self.invoice, second_invoice], receipts=receipts)
        self.assertEqual(result['findings'], [])
        self.assertFalse(result['truncated'])
        json.dumps(result)

    def test_aggregate_overbilling_uses_group_not_individual_invoice(self):
        second = ['i2', 'v1', 'INV-2', 'po1', '70', 'USD', 'reviewer', 'payer', 'invoice:2']
        result = self.run_check(invoices=[self.invoice, second])
        over = self.by_rule(result, 'po_overbilled')
        self.assertEqual(len(over), 1)
        self.assertEqual(over[0]['details']['invoice_total'], '110')
        self.assertEqual(over[0]['details']['po_authorized'], '100')
        receipt_finding = self.by_rule(result, 'billed_exceeds_receipts')
        self.assertEqual(len(receipt_finding), 1)
        self.assertEqual(receipt_finding[0]['details']['receipt_total'], '100')
        self.assertEqual({ref['record_id'] for ref in over[0]['references']}, {'po1', 'i1', 'i2'})

    def test_exact_aggregation_detects_difference_beyond_decimal_context_precision(self):
        self.po[2] = '99999999999999999999.999999999999999997'
        self.invoice[4] = self.po[2]
        self.receipt[3] = self.po[2]
        extra = ['i2', 'v1', 'INV-2', 'po1', '0.000000000000000001', 'USD', 'a', 'b', 'invoice:2']
        result = self.run_check(invoices=[self.invoice, extra])
        self.assertEqual(self.by_rule(result, 'po_overbilled')[0]['details']['invoice_total'],
                         '99999999999999999999.999999999999999998')

    def test_invoice_vendor_and_currency_mismatch_do_not_enter_comparable_totals(self):
        wrong_vendor = ['i2', 'v2', 'INV-2', 'po1', '999', 'USD', 'a', 'b', 'invoice:2']
        wrong_currency = ['i3', 'v1', 'INV-3', 'po1', '999', 'VND', 'a', 'b', 'invoice:3']
        result = self.run_check(invoices=[self.invoice, wrong_vendor, wrong_currency])
        self.assertEqual(len(self.by_rule(result, 'invoice_po_mismatch')), 2)
        self.assertEqual(self.by_rule(result, 'po_overbilled'), [])
        self.assertEqual(self.by_rule(result, 'billed_exceeds_receipts'), [])

    def test_receipt_mismatch_does_not_supply_matching_evidence(self):
        receipts = [['r1', 'po1', 'v2', '999', 'USD', 'receipt:1'],
                    ['r2', 'po1', 'v1', '999', 'VND', 'receipt:2']]
        result = self.run_check(receipts=receipts)
        self.assertEqual(len(self.by_rule(result, 'receipt_po_mismatch')), 2)
        self.assertEqual(len(self.by_rule(result, 'missing_receipt_evidence')), 1)
        self.assertEqual(self.by_rule(result, 'billed_exceeds_receipts'), [])

    def test_absent_and_unreferenced_po_and_missing_receipts_remain_distinct(self):
        no_reference = ['i2', 'v1', 'INV-2', '', '10', 'USD', 'a', 'b', 'invoice:2']
        unknown_reference = ['i3', 'v1', 'INV-3', 'missing', '10', 'USD', 'a', 'b', 'invoice:3']
        result = self.run_check(invoices=[self.invoice, no_reference, unknown_reference], receipts=[])
        self.assertEqual(len(self.by_rule(result, 'missing_po_reference')), 1)
        self.assertEqual(len(self.by_rule(result, 'po_not_found')), 1)
        self.assertEqual(len(self.by_rule(result, 'missing_receipt_evidence')), 1)

    def test_duplicate_vendor_invoice_reference_is_not_duplicate_payment_proof(self):
        second = ['i2', 'v1', 'INV-1', 'po1', '40', 'USD', 'a', 'b', 'invoice:2']
        other_vendor = ['i3', 'v2', 'INV-1', '', '40', 'USD', 'a', 'b', 'invoice:3']
        result = self.run_check(invoices=[self.invoice, second, other_vendor])
        duplicate = self.by_rule(result, 'duplicate_invoice_reference')
        self.assertEqual(len(duplicate), 1)
        self.assertEqual({ref['record_id'] for ref in duplicate[0]['references']}, {'i1', 'i2'})
        self.assertIn('not proof of duplicate payment', duplicate[0]['summary'])

    def test_approval_gaps_and_role_overlap_have_evidence(self):
        self.invoice[6] = self.invoice[7] = 'same'
        self.po[4] = self.po[5] = 'same'
        blank = ['i2', 'v1', '', 'po1', '10', 'USD', '', '', 'invoice:2']
        result = self.run_check(invoices=[self.invoice, blank])
        self.assertEqual(len(self.by_rule(result, 'invoice_approval_overlap')), 1)
        self.assertEqual(len(self.by_rule(result, 'po_approval_overlap')), 1)
        self.assertEqual(len(self.by_rule(result, 'missing_invoice_approval')), 1)
        self.assertEqual(len(self.by_rule(result, 'missing_invoice_number')), 1)

    def test_missing_po_approver_is_a_gap(self):
        self.po[5] = ''
        result = self.run_check()
        self.assertEqual(len(self.by_rule(result, 'missing_po_approval')), 1)

    def test_purchase_and_payment_approval_overlap_links_both_sources(self):
        self.po[5] = 'payer'
        result = self.run_check()
        matches = self.by_rule(result, 'purchase_payment_approval_overlap')
        self.assertEqual(len(matches), 1)
        self.assertEqual(matches[0]['details']['approver'], 'payer')
        self.assertEqual({ref['table'] for ref in matches[0]['references']},
                         {'invoices', 'purchase_orders'})
        self.assertEqual({ref['record_id'] for ref in matches[0]['references']},
                         {'i1', 'po1'})

    def test_purchase_payment_approval_does_not_match_blank_or_different_ids(self):
        for purchase, payment in [('', ''), ('manager', 'payer'), ('Payer', 'payer')]:
            self.po[5] = purchase
            self.invoice[7] = payment
            with self.subTest(purchase=purchase, payment=payment):
                self.assertEqual(self.by_rule(self.run_check(), 'purchase_payment_approval_overlap'), [])

    def test_source_hash_rows_and_evidence_refs_cover_aggregate_inputs(self):
        self.invoice[4] = '110'
        result = self.run_check()
        finding = self.by_rule(result, 'billed_exceeds_receipts')[0]
        self.assertEqual(len(finding['references']), 3)
        for ref in finding['references']:
            source = result['sources'][ref['table']]
            expected_hash = hashlib.sha256((self.root / source['file_name']).read_bytes()).hexdigest()
            self.assertEqual(ref['source_sha256'], expected_hash)
            self.assertEqual(ref['source_row'], 2)
            self.assertTrue(ref['evidence_ref'])

    def test_cap_bounds_findings_and_reports_truncation(self):
        self.invoice[3] = ''
        self.invoice[6] = self.invoice[7] = ''
        result = self.run_check(max_findings=1)
        self.assertEqual(len(result['findings']), 1)
        self.assertTrue(result['truncated'])
        with self.assertRaises(ValueError):
            self.run_check(max_findings=0)

    def test_duplicate_primary_keys_rejected_in_each_table(self):
        for kwargs in [dict(invoices=[self.invoice, self.invoice]),
                       dict(pos=[self.po, self.po]), dict(receipts=[self.receipt, self.receipt])]:
            with self.subTest(kwargs=kwargs), self.assertRaises(ValueError):
                self.run_check(**kwargs)

    def test_missing_currency_ids_evidence_and_unbounded_amounts_rejected(self):
        for column, value in [(0, ''), (1, ''), (5, ''), (8, ''), (4, '1e1000000000')]:
            bad = list(self.invoice)
            bad[column] = value
            with self.subTest(column=column), self.assertRaises(ValueError):
                self.run_check(invoices=[bad])

    def test_validation_continues_even_after_enough_findings(self):
        self.invoice[3] = ''
        bad = ['i2', '', 'INV-2', '', '10', 'USD', '', '', 'invoice:2']
        with self.assertRaises(ValueError):
            self.run_check(invoices=[self.invoice, bad], max_findings=1)


if __name__ == '__main__':
    unittest.main()
