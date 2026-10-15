import csv
import json
import sqlite3
import tempfile
import unittest
from pathlib import Path

from embezzlement_analysis.batch import scan_dataset
from embezzlement_analysis.ingest import IBM_HEADER, ingest_csv


class BatchTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.db = self.root / 'case.sqlite'
        self.accounts = self.root / 'accounts.csv'
        self.account_rows = [
            ['Bank', '01', 'company', 'A', 'Corporation A'],
            ['Bank', '1', 'middle', 'B', 'Corporation B'],
            ['Bank', '1', 'person', 'C', 'Individual C'],
            ['Bank', '1', 'company2', 'A', 'Corporation A'],
            ['Bank', '1', 'unknown', 'U', 'Unrecognized U'],
        ]
        self.write_accounts()

    def write_accounts(self):
        with self.accounts.open('w', newline='') as file:
            writer = csv.writer(file)
            writer.writerow(['Bank Name', 'Bank ID', 'Account Number', 'Entity ID', 'Entity Name'])
            writer.writerows(self.account_rows)

    def tx(self, sender, recipient, day=1, hour=0, paid='100', received=None,
           currency='USD', receiving=None, label=0):
        return ['2024/01/%02d %02d:00' % (day, hour), '1', sender, '1', recipient,
                received or paid, receiving or currency, paid, currency, 'ACH', str(label)]

    def ingest(self, rows):
        path = self.root / 'transactions.csv'
        with path.open('w', newline='') as file:
            writer = csv.writer(file)
            writer.writerow(IBM_HEADER)
            writer.writerows(rows)
        ingest_csv(path, self.db)

    def scan(self, name='paths.jsonl', **kwargs):
        output = self.root / name
        summary = scan_dataset(self.db, self.accounts, output, **kwargs)
        lines = [json.loads(line) for line in output.read_text().splitlines()]
        return summary, lines

    def test_full_scan_provenance_unique_edges_and_examples(self):
        self.ingest([self.tx('company', 'middle'),
                     self.tx('middle', 'person', hour=1),
                     self.tx('middle', 'person', hour=2)])
        before = self.db.read_bytes()
        summary, paths = self.scan(max_examples=1)
        self.assertEqual(summary['candidate_count'], 2)
        self.assertEqual(len(paths), 2)
        self.assertEqual(summary['unique_first_edges'], 1)
        self.assertEqual(summary['unique_second_edges'], 2)
        self.assertEqual(len(summary['examples']), 1)
        self.assertEqual(summary['examples'][0], paths[0])
        self.assertFalse(summary['truncated'])
        self.assertTrue(summary['full_coverage'])
        self.assertEqual(summary['coverage']['transaction_count'], 3)
        self.assertEqual([edge['id'] for edge in paths[0]['path']], [1, 2])
        self.assertEqual(paths[0]['path'][0]['source_row'], 2)
        self.assertEqual(len(paths[0]['path'][0]['source_sha256']), 64)
        self.assertNotIn('is_laundering', paths[0]['path'][0])
        self.assertEqual(before, self.db.read_bytes())

    def test_label_changes_only_affect_post_selection_diagnostics(self):
        self.ingest([self.tx('company', 'middle'), self.tx('middle', 'person', hour=1)])
        before, paths_before = self.scan()
        with sqlite3.connect(self.db) as conn:
            conn.execute('UPDATE transactions SET is_laundering=1')
        after, paths_after = self.scan('after.jsonl')
        self.assertEqual(paths_before, paths_after)
        self.assertEqual(before['examples'], after['examples'])
        self.assertEqual(before['label_diagnostics']['none_labeled'], 1)
        self.assertEqual(after['label_diagnostics']['all_labeled'], 1)
        self.assertEqual(before['candidate_count'], after['candidate_count'])

    def test_strict_time_currency_window_and_exact_ratio(self):
        self.ingest([
            self.tx('company', 'middle', received='1000000', receiving='VND'),
            self.tx('middle', 'person', hour=0, paid='800000', currency='VND'),
            self.tx('middle', 'person', hour=1, paid='800000', currency='USD'),
            self.tx('middle', 'person', hour=2, paid='799999.999999999999999999', currency='VND'),
            self.tx('middle', 'person', day=4, hour=0, paid='1050000', currency='VND'),
            self.tx('middle', 'person', day=4, hour=1, paid='1000000', currency='VND'),
        ])
        summary, paths = self.scan()
        self.assertEqual(summary['candidate_count'], 1)
        self.assertEqual([edge['id'] for edge in paths[0]['path']], [1, 5])
        self.assertEqual(summary['examined']['time_currency_role_pairs'], 2)
        self.assertEqual(summary['examined']['ratio_rejected_pairs'], 1)

    def test_unknown_and_missing_accounts_are_explicit_coverage_gaps(self):
        self.ingest([self.tx('company', 'unknown'),
                     self.tx('unknown', 'person', hour=1),
                     self.tx('missing', 'person', hour=2)])
        summary, paths = self.scan()
        self.assertEqual(paths, [])
        self.assertEqual(summary['coverage']['missing_sender_metadata'], 1)
        self.assertEqual(summary['coverage']['unknown_sender_role'], 1)
        self.assertEqual(summary['coverage']['unknown_recipient_role'], 1)

    def test_same_owner_and_same_account_paths_excluded_with_diagnostics(self):
        self.ingest([self.tx('company', 'company2'),
                     self.tx('company2', 'person', hour=1),
                     self.tx('middle', 'middle'),
                     self.tx('middle', 'person', hour=1)])
        summary, paths = self.scan()
        self.assertEqual(paths, [])
        self.assertEqual(summary['examined']['same_entity_pairs'], 2)
        self.assertEqual(summary['examined']['same_account_pairs'], 1)
        self.assertEqual(summary['examined']['ownership_excluded_pairs'], 2)

    def test_labels_all_some_none_count_after_selection(self):
        self.ingest([self.tx('company', 'middle', label=1),
                     self.tx('middle', 'person', hour=1, label=1),
                     self.tx('middle', 'person', hour=2, label=0)])
        summary, _ = self.scan()
        self.assertEqual(summary['label_diagnostics'],
                         {'all_labeled': 1, 'some_labeled': 1, 'none_labeled': 0})

    def test_postselection_unique_edges_denominators_and_main_tail_actual_labels(self):
        rows = [self.tx('company', 'middle', label=1),
                self.tx('middle', 'person', label=1),
                self.tx('middle', 'person', label=0),
                self.tx('unknown', 'person', label=1)]
        for row, timestamp in zip(rows, ['2022/09/10 22:00', '2022/09/10 23:00',
                                        '2022/09/11 00:00', '2022/09/11 01:00']):
            row[0] = timestamp
        self.ingest(rows)
        summary, paths = self.scan()
        self.assertEqual(len(paths), 2)
        self.assertEqual(summary['selected_edge_diagnostics'],
                         {'total': 3, 'laundering': 2, 'not_laundering': 1})
        self.assertEqual(summary['ledger_label_diagnostics'],
                         {'total': 4, 'laundering': 3, 'not_laundering': 1})
        phases = summary['phase_label_diagnostics']
        self.assertEqual(phases['cutoff'], '2022-09-11T00:00:00')
        self.assertEqual(phases['main_window'],
                         {'candidate_count': 1, 'all_labeled': 1, 'some_labeled': 0, 'none_labeled': 0})
        self.assertEqual(phases['contains_tail'],
                         {'candidate_count': 1, 'all_labeled': 0, 'some_labeled': 1, 'none_labeled': 0})

    def test_empty_selection_has_zero_postselection_diagnostics(self):
        self.ingest([self.tx('unknown', 'person', label=1)])
        summary, paths = self.scan()
        self.assertEqual(paths, [])
        self.assertEqual(summary['selected_edge_diagnostics'],
                         {'total': 0, 'laundering': 0, 'not_laundering': 0})
        self.assertEqual(summary['phase_label_diagnostics']['contains_tail']['candidate_count'], 0)

    def test_duplicate_accounts_and_entity_conflicts_reject_without_output(self):
        self.ingest([self.tx('company', 'middle')])
        self.account_rows.append(self.account_rows[0])
        self.write_accounts()
        with self.assertRaises(ValueError):
            self.scan()
        self.assertFalse((self.root / 'paths.jsonl').exists())
        self.account_rows[-1] = ['Bank', '1', 'different', 'A', 'Individual A']
        self.write_accounts()
        with self.assertRaises(ValueError):
            self.scan()

    def test_output_never_overwrites_existing_file_and_examples_can_be_zero(self):
        self.ingest([self.tx('company', 'middle'), self.tx('middle', 'person', hour=1)])
        summary, paths = self.scan(max_examples=0)
        self.assertEqual(summary['examples'], [])
        self.assertEqual(len(paths), 1)
        before = (self.root / 'paths.jsonl').read_bytes()
        with self.assertRaises(FileExistsError):
            self.scan()
        self.assertEqual((self.root / 'paths.jsonl').read_bytes(), before)

    def test_person_edge_prefilter_preserves_hand_checked_global_candidates(self):
        self.ingest([self.tx('company', 'middle'),
                     self.tx('middle', 'company2', hour=1),
                     self.tx('middle', 'person', hour=2),
                     self.tx('unknown', 'person', hour=3),
                     self.tx('middle', 'person', hour=4, currency='VND'),
                     self.tx('company2', 'person', hour=5)])
        summary, paths = self.scan()
        self.assertEqual([[edge['id'] for edge in item['path']] for item in paths], [[1, 3], [2, 6]])
        # Four person-ending edges survive the cheap role-only prefilter;
        # sender role and adjacent currency still reject two during selection.
        self.assertEqual(summary['coverage']['onward_person_edge_count'], 4)
        self.assertTrue(any('SEARCH e2 USING INDEX onward_person_sender_time' in step
                            for step in summary['query_plan']))


if __name__ == '__main__':
    unittest.main()
