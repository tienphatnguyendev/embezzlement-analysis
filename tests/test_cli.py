import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]


class CliTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.db = str(Path(self.tmp.name) / 'demo.sqlite')

    def run_cli(self, *args):
        return subprocess.run([sys.executable, '-m', 'embezzlement_analysis', *args], cwd=ROOT, text=True, capture_output=True)

    def test_end_to_end_demo_distinguishes_context_not_guilt(self):
        imported = self.run_cli('ingest', 'examples/demo_transactions.csv', '--db', self.db)
        self.assertEqual(imported.returncode, 0, imported.stderr)
        result = self.run_cli('trace', '--db', self.db, '--bank', '001', '--account', 'VICTIM', '--context', 'examples/demo_context.csv')
        self.assertEqual(result.returncode, 0, result.stderr)
        report = json.loads(result.stdout)
        self.assertEqual(len(report['findings']), 3)
        self.assertFalse(report['truncated'])
        linked = [f for f in report['findings'] if 'recipient_employee_of_origin' in f['review_signals']]
        self.assertEqual(len(linked), 2)
        self.assertTrue(report['sources'][0]['sha256'])
        self.assertTrue(report['context_source']['sha256'])
        self.assertNotIn('is_laundering', result.stdout)
        self.assertEqual(report['conclusion'], 'Candidate paths for review; embezzlement is not established.')

    def test_missing_database_errors_without_creating_file(self):
        result = self.run_cli('trace', '--db', self.db, '--bank', '1', '--account', 'A')
        self.assertEqual(result.returncode, 2)
        self.assertFalse(Path(self.db).exists())

    def test_report_does_not_overwrite_existing_evidence(self):
        imported = self.run_cli('ingest', 'examples/demo_transactions.csv', '--db', self.db)
        self.assertEqual(imported.returncode, 0, imported.stderr)
        target = Path(self.tmp.name) / 'report.json'
        target.write_text('original')
        result = self.run_cli('trace', '--db', self.db, '--bank', '1', '--account', 'VICTIM', '--output', str(target))
        self.assertEqual(result.returncode, 2)
        self.assertEqual(target.read_text(), 'original')

    def test_bad_ratio_gives_actionable_error_without_traceback(self):
        for option in ['--min-ratio', '--max-ratio']:
            with self.subTest(option=option):
                result = self.run_cli('trace', '--db', self.db, '--bank', '1', '--account', 'A', option, 'nonsense')
                self.assertEqual(result.returncode, 2)
                self.assertNotIn('Traceback', result.stderr)
                self.assertIn('number', result.stderr)
