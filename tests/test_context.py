import csv
import hashlib
import tempfile
import unittest
from pathlib import Path

from embezzlement_analysis.context import load_context, annotate_paths


HEADER = ['bank', 'account', 'entity_id', 'entity_type', 'entity_name', 'employee_of', 'evidence_ref']


class ContextTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name) / 'context.csv'

    def write(self, rows):
        with self.path.open('w', newline='') as stream:
            writer = csv.writer(stream)
            writer.writerow(HEADER)
            writer.writerows(rows)

    def test_link_uses_entity_id_and_preserves_evidence(self):
        self.write([
            ['001', '000A', 'employer', 'business', 'Example business', '', 'fixture:company'],
            ['2', 'B', 'vendor', 'business', 'Example supplier', '', 'fixture:vendor'],
            ['3', 'C', 'worker', 'person', 'Example person', 'employer', 'fixture:hr'],
        ])
        context = load_context(self.path)
        paths = [[{'from_bank': '1', 'from_account': '000A', 'to_bank': '2', 'to_account': 'B'},
                  {'from_bank': '2', 'from_account': 'B', 'to_bank': '3', 'to_account': 'C'}]]
        result = annotate_paths(paths, context)[0]
        self.assertIn('recipient_employee_of_origin', result['review_signals'])
        self.assertEqual(result['accounts'][-1]['evidence_ref'], 'fixture:hr')
        self.assertNotIn('fraud', result['review_signals'])

    def test_unknown_does_not_become_person(self):
        result = annotate_paths([[{'from_bank': '1', 'from_account': 'A', 'to_bank': '2', 'to_account': 'B'}]], {})[0]
        self.assertEqual(result['review_signals'], [])
        self.assertEqual(result['accounts'][-1]['entity_type'], 'unknown')

    def test_rejects_duplicate_normalized_key(self):
        self.write([['01', 'A', 'e', 'business', 'E', '', 'ref'], ['1', 'A', 'f', 'person', 'F', '', 'ref']])
        with self.assertRaises(ValueError):
            load_context(self.path)

    def test_requires_source_for_asserted_context(self):
        self.write([['1', 'A', 'e', 'business', 'E', '', '']])
        with self.assertRaises(ValueError):
            load_context(self.path)

    def test_benign_supplier_payroll_has_no_origin_employee_link(self):
        self.write([['1', 'A', 'buyer', 'business', 'Buyer', '', 'ref'],
                    ['3', 'C', 'worker', 'person', 'Worker', 'supplier', 'ref']])
        result = annotate_paths([[{'from_bank': '1', 'from_account': 'A', 'to_bank': '3', 'to_account': 'C'}]], load_context(self.path))[0]
        self.assertIn('business_to_person', result['review_signals'])
        self.assertNotIn('recipient_employee_of_origin', result['review_signals'])

    def test_rejects_conflicting_entity_type_across_accounts(self):
        self.write([['1', 'A', 'same', 'business', 'E', '', 'ref'],
                    ['2', 'B', 'same', 'person', 'E', '', 'ref']])
        with self.assertRaises(ValueError):
            load_context(self.path)

    def test_account_identity_whitespace_is_not_silently_changed(self):
        self.write([['1', ' A ', 'e', 'business', 'E', '', 'ref']])
        context = load_context(self.path)
        self.assertIn(('1', ' A '), context)
        self.assertNotIn(('1', 'A'), context)

    def test_snapshot_hash_covers_exact_parsed_bytes(self):
        from embezzlement_analysis.context import load_context_snapshot
        self.write([['1', 'A', 'e', 'business', 'E', '', 'ref']])
        original = self.path.read_bytes()
        context, source = load_context_snapshot(self.path)
        self.path.write_text('changed after snapshot')
        self.assertEqual(source['sha256'], hashlib.sha256(original).hexdigest())
        self.assertEqual(context[('1', 'A')]['evidence_ref'], 'ref')
