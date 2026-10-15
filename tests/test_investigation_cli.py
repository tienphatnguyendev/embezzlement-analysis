import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class InvestigationCliTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.db = str(Path(self.tmp.name) / 'case.sqlite')

    def command(self, *args):
        return subprocess.run([sys.executable, '-m', 'embezzlement_analysis', *args],
                              cwd=ROOT, capture_output=True, text=True)

    def test_master_and_invoice_commands_keep_source_evidence(self):
        cases = [
            ('check-masters', '--vendors', 'examples/vendors.csv', '--employees', 'examples/employees.csv'),
            ('check-invoices', '--invoices', 'examples/invoices.csv', '--purchase-orders', 'examples/purchase_orders.csv', '--receipts', 'examples/receipts.csv'),
        ]
        for args in cases:
            with self.subTest(command=args[0]):
                result = self.command(*args)
                self.assertEqual(result.returncode, 0, result.stderr)
                report = json.loads(result.stdout)
                self.assertTrue(report['findings'])
                self.assertTrue(report['sources'])
                self.assertFalse(report['truncated'])

    def test_combined_report_integrates_all_checks(self):
        imported = self.command('ingest', 'examples/demo_transactions.csv', '--db', self.db)
        self.assertEqual(imported.returncode, 0, imported.stderr)
        result = self.command('investigate', '--db', self.db, '--bank', '1', '--account', 'VICTIM',
                              '--context', 'examples/demo_context.csv', '--ibm-accounts', 'examples/ibm_accounts.csv',
                              '--vendors', 'examples/vendors.csv', '--employees', 'examples/employees.csv',
                              '--invoices', 'examples/invoices.csv', '--purchase-orders', 'examples/purchase_orders.csv',
                              '--receipts', 'examples/receipts.csv')
        self.assertEqual(result.returncode, 0, result.stderr)
        report = json.loads(result.stdout)
        self.assertEqual(len(report['findings']), 3)
        self.assertTrue(report['master_checks']['findings'])
        self.assertTrue(report['invoice_checks']['findings'])
        self.assertTrue(report['ibm_accounts_source']['sha256'])
        self.assertTrue(report['path_vendor_links'])
        self.assertTrue(any(link['invoice_finding_indices'] and link['master_finding_indices']
                            for link in report['path_vendor_links']))
        self.assertFalse(report['truncated'])
        self.assertNotIn('is_laundering', result.stdout)

    def test_source_errors_are_readable_and_do_not_leave_report(self):
        target = Path(self.tmp.name) / 'report.json'
        result = self.command('check-masters', '--vendors', 'absent.csv', '--employees', 'examples/employees.csv', '--output', str(target))
        self.assertEqual(result.returncode, 2)
        self.assertNotIn('Traceback', result.stderr)
        self.assertFalse(target.exists())

    def test_saved_combined_summary_counts_each_section(self):
        self.command('ingest', 'examples/demo_transactions.csv', '--db', self.db)
        target = Path(self.tmp.name) / 'case.json'
        result = self.command('investigate', '--db', self.db, '--bank', '1', '--account', 'VICTIM',
                              '--vendors', 'examples/vendors.csv', '--employees', 'examples/employees.csv',
                              '--invoices', 'examples/invoices.csv', '--purchase-orders', 'examples/purchase_orders.csv',
                              '--receipts', 'examples/receipts.csv', '--output', str(target))
        self.assertEqual(result.returncode, 0, result.stderr)
        summary, report = json.loads(result.stdout), json.loads(target.read_text())
        self.assertEqual(summary['candidate_paths'], len(report['findings']))
        self.assertEqual(summary['master_findings'], len(report['master_checks']['findings']))
        self.assertEqual(summary['invoice_findings'], len(report['invoice_checks']['findings']))
        self.assertEqual(summary['finding_count'], summary['candidate_paths'] + summary['master_findings'] + summary['invoice_findings'])
