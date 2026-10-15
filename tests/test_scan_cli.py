import csv
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from embezzlement_analysis.accounts import FIELDS
from embezzlement_analysis.ingest import IBM_HEADER, ingest_csv


class ScanCliTests(unittest.TestCase):
    def test_scan_writes_candidate_rows_and_summary(self):
        with tempfile.TemporaryDirectory() as folder:
            folder = Path(folder)
            transactions, accounts = folder / 'transactions.csv', folder / 'accounts.csv'
            with transactions.open('w', newline='') as stream:
                writer = csv.writer(stream)
                writer.writerow(IBM_HEADER)
                writer.writerows([
                    ['2022/09/01 10:00', '1', 'A', '2', 'B', '100', 'USD', '100', 'USD', 'Wire', '0'],
                    ['2022/09/01 11:00', '2', 'B', '3', 'C', '98', 'USD', '98', 'USD', 'Wire', '0'],
                ])
            with accounts.open('w', newline='') as stream:
                writer = csv.writer(stream)
                writer.writerow(FIELDS)
                writer.writerows([['Bank1', '1', 'A', 'company1', 'Corporation #1'],
                                  ['Bank2', '2', 'B', 'company2', 'Corporation #2'],
                                  ['Bank3', '3', 'C', 'person1', 'Individual #1']])
            database = folder / 'case.sqlite'
            ingest_csv(transactions, database)
            candidates, summary = folder / 'paths.jsonl', folder / 'summary.json'
            result = subprocess.run([
                sys.executable, '-m', 'embezzlement_analysis', 'scan', '--db', str(database),
                '--ibm-accounts', str(accounts), '--candidates', str(candidates), '--output', str(summary),
            ], text=True, capture_output=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            report = json.loads(summary.read_text())
            self.assertFalse(report['truncated'])
            self.assertEqual(report['candidate_count'], 1)
            self.assertEqual(len(candidates.read_text().splitlines()), 1)
            self.assertNotIn('is_laundering', candidates.read_text())
