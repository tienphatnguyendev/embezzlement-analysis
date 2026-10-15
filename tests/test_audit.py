import csv
import hashlib
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from embezzlement_analysis.audit import ACCOUNT_HEADER, TX_HEADER, audit_accounts, audit_transactions, audit_patterns


class AuditTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def write(self, name, header, rows):
        path = self.root / name
        with path.open('w', newline='') as stream:
            writer = csv.writer(stream)
            writer.writerow(header)
            writer.writerows(rows)
        return path

    def test_metadata_duplicates_conflicts_and_exact_identity(self):
        path = self.write('accounts.csv', ACCOUNT_HEADER, [
            ['Bank', '001', '000A', 'e1', 'Corporation #1'],
            ['Bank', '1', '000A', 'e1', 'Corporation #1'],
            ['Bank', '1', '000A', 'e2', 'Individual #1'],
            ['Bank', '1', ' A ', 'e3', 'Unrecognized']])
        report, mapping, conflicts = audit_accounts(path)
        self.assertEqual(report['rows'], 4)
        self.assertEqual(report['unique_account_keys'], 2)
        self.assertEqual(report['identical_duplicate_key_rows'], 1)
        self.assertEqual(report['conflicting_duplicate_key_rows'], 1)
        self.assertEqual(conflicts, {('1', '000A')})
        self.assertIn(('1', ' A '), mapping)

    def test_daily_label_counts_and_normalized_join_coverage(self):
        path = self.write('tx.csv', TX_HEADER, [
            ['2022/09/10 23:59', '001', '000A', '2', 'B', '100', 'USD', '100', 'USD', 'ACH', '0'],
            ['2022/09/11 00:01', '002', 'B', '3', 'C', '90', 'USD', '90', 'USD', 'ACH', '1']])
        accounts = {('1', '000A'): ('e1', 'Corporation #1'), ('2', 'B'): ('e2', 'Individual #1')}
        report = audit_transactions(path, accounts, set(), '2022-09-10')
        self.assertEqual(report['rows'], 2)
        self.assertEqual(report['label_counts'], {'0': 1, '1': 1})
        self.assertEqual(report['after_publisher_main_window']['rows'], 1)
        self.assertEqual(report['after_publisher_main_window']['label_counts'], {'1': 1})
        self.assertEqual(report['endpoint_occurrence_coverage']['unambiguous_metadata'], 3)
        self.assertEqual(report['endpoint_occurrence_coverage']['missing_metadata'], 1)
        self.assertEqual(report['unique_accounts_in_transactions'], 3)

    def test_pattern_blocks_include_types_rows_and_structural_errors(self):
        path = self.root / 'patterns.txt'
        path.write_text('BEGIN LAUNDERING ATTEMPT - FAN-OUT: max degree 2\n'
                        '2022/09/01 00:00,1,A,1,B,1,USD,1,USD,ACH,1\n'
                        'END LAUNDERING ATTEMPT - FAN-OUT\n')
        report, signatures = audit_patterns(path)
        self.assertEqual(report['attempts'], 1)
        self.assertEqual(report['attempt_types'], {'FAN-OUT': 1})
        self.assertEqual(report['transaction_rows'], 1)
        self.assertEqual(report['label_counts'], {'1': 1})
        self.assertEqual(report['structural_errors'], [])
        self.assertEqual(len(signatures), 1)

    def test_module_command_writes_reports_with_file_hashes(self):
        transaction = ['2022/09/01 00:00', '1', 'A', '1', 'B', '1', 'USD', '1', 'USD', 'ACH', '1']
        tx = self.write('HI-Small_Trans.csv', TX_HEADER, [transaction])
        self.write('HI-Small_accounts.csv', ACCOUNT_HEADER,
                   [['Bank', '1', 'A', 'e1', 'Corporation #1'],
                    ['Bank', '1', 'B', 'e2', 'Individual #1']])
        (self.root / 'HI-Small_Patterns.txt').write_text(
            'BEGIN LAUNDERING ATTEMPT - RANDOM\n' + ','.join(transaction)
            + '\nEND LAUNDERING ATTEMPT - RANDOM\n')
        output, notes = self.root / 'audit.json', self.root / 'notes.md'
        result = subprocess.run(
            [sys.executable, '-m', 'embezzlement_analysis.audit', '--input-dir', str(self.root),
             '--output', str(output), '--notes', str(notes)],
            cwd=Path(__file__).resolve().parents[1], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        report = json.loads(output.read_text())
        self.assertEqual(report['sources']['transactions']['sha256'], hashlib.sha256(tx.read_bytes()).hexdigest())
        self.assertEqual(report['transactions']['pattern_transaction_rows_found'], 1)
        self.assertTrue(notes.exists())


if __name__ == '__main__':
    unittest.main()
