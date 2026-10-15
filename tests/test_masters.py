import csv
import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from embezzlement_analysis.masters import analyze_masters


VENDORS = ['vendor_id', 'name', 'bank', 'account', 'address', 'tax_id', 'evidence_ref']
EMPLOYEES = ['employee_id', 'employer_entity_id', 'name', 'bank', 'account',
             'address', 'tax_id', 'evidence_ref']


class MastersTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.vendors = Path(self.tmp.name) / 'vendors.csv'
        self.employees = Path(self.tmp.name) / 'employees.csv'

    def write(self, vendors, employees):
        for path, fields, rows in ((self.vendors, VENDORS, vendors),
                                   (self.employees, EMPLOYEES, employees)):
            with path.open('w', encoding='utf-8', newline='') as stream:
                writer = csv.writer(stream)
                writer.writerow(fields)
                writer.writerows(rows)

    def analyze(self, **kwargs):
        return analyze_masters(self.vendors, self.employees, **kwargs)

    def overlaps(self, report):
        return [f for f in report['findings'] if f['rule_id'] == 'vendor_employee_overlap']

    def test_composite_account_match_preserves_ids_and_full_provenance(self):
        self.write([['000V', 'Supplier', '001', '000A', '1 Vendor Road', '001T', 'doc:v']],
                   [['000E', '000B', 'Employee', '1', '000A', '2 Home Road', '002T', 'doc:e']])
        report = self.analyze()
        finding = self.overlaps(report)[0]
        self.assertEqual(finding['matched_fields'], ['bank_account'])
        self.assertEqual(finding['matched_values'], {'bank_account': {'bank': '1', 'account': '000A'}})
        self.assertEqual((finding['vendor_id'], finding['employee_id'], finding['employer_entity_id']),
                         ('000V', '000E', '000B'))
        self.assertEqual(finding['specificity'], 'stronger')
        for key, path, ref in [('vendor', self.vendors, 'doc:v'), ('employee', self.employees, 'doc:e')]:
            self.assertEqual(finding[key]['evidence_ref'], ref)
            self.assertEqual(finding[key]['source_row'], 2)
            self.assertEqual(finding[key]['source_sha256'], hashlib.sha256(path.read_bytes()).hexdigest())
            self.assertEqual(finding[key]['source_file'], path.name)
        self.assertEqual(finding['vendor']['bank'], '001')
        self.assertEqual(report['sources'][0]['row_count'], 1)
        self.assertFalse(report['truncated'])
        self.assertIsInstance(json.dumps(report), str)

    def test_blanks_never_match_and_vendor_gaps_are_explicit(self):
        self.write([['v', '', '', '', '  ', '', 'doc:v']],
                   [['e', 'buyer', '', '', '', '', '', 'doc:e']])
        report = self.analyze()
        self.assertEqual(self.overlaps(report), [])
        self.assertEqual(len(report['findings']), 1)
        finding = report['findings'][0]
        self.assertEqual(finding['rule_id'], 'incomplete_vendor_profile')
        self.assertEqual(finding['missing_fields'], ['bank', 'address', 'tax_id'])
        self.assertEqual(finding['vendor']['source_row'], 2)

    def test_same_account_at_different_bank_does_not_match(self):
        self.write([['v', 'Vendor', '1', '000A', 'A Road', 'T1', 'vref']],
                   [['e', 'buyer', 'Worker', '2', '000A', 'B Road', 'T2', 'eref']])
        self.assertEqual(self.analyze()['findings'], [])

    def test_description_normalization_only_and_name_only_is_weak(self):
        self.write([['v', '  Alex   Smith ', '1', 'A', '10 ROAD', '001', 'vref']],
                   [['e', 'buyer', 'alex smith', '2', 'B', '11 road', '1', 'eref']])
        finding = self.overlaps(self.analyze())[0]
        self.assertEqual(finding['matched_fields'], ['name'])
        self.assertEqual(finding['matched_values']['name'], 'alex smith')
        self.assertEqual(finding['specificity'], 'weak')
        self.assertEqual(finding['vendor']['name'], '  Alex   Smith ')

    def test_multiple_employees_and_multiple_matches_produce_one_pair_each(self):
        self.write([['v', 'Common', '1', 'A', ' 10  Road ', 'T', 'vref']],
                   [['e1', 'buyer', 'common', '01', 'A', '10 road', 'T', 'e1ref'],
                    ['e2', 'other-employer', 'Someone', '2', 'B', '10 ROAD', 'X', 'e2ref']])
        findings = self.overlaps(self.analyze())
        self.assertEqual([f['employee_id'] for f in findings], ['e1', 'e2'])
        self.assertEqual(findings[0]['matched_fields'], ['bank_account', 'tax_id', 'address', 'name'])
        self.assertEqual(findings[1]['matched_fields'], ['address'])
        self.assertEqual(findings[1]['employer_entity_id'], 'other-employer')

    def test_exact_identifiers_are_not_stripped_or_casefolded(self):
        self.write([[' v ', 'Vendor', '1', ' A ', 'Street A', ' t ', 'vref']],
                   [[' e ', ' buyer ', 'Employee', '1', 'A', 'Street B', 't', 'eref']])
        self.assertEqual(self.analyze()['findings'], [])

    def test_punctuation_and_street_abbreviations_do_not_merge_lookalikes(self):
        self.write([['v', 'Alex Smith', '1', 'A', '10 Main Street', 'T1', 'vref']],
                   [['e', 'buyer', 'Alex-Smith', '2', 'B', '10 Main St.', 'T2', 'eref']])
        self.assertEqual(self.analyze()['findings'], [])

    def test_duplicate_record_ids_rejected_even_beyond_result_cap(self):
        for duplicate_kind in ('vendor', 'employee'):
            with self.subTest(kind=duplicate_kind):
                vendors = [['v', 'Common', '1', 'A', 'Street', 'T', 'vref']]
                employees = [['e', 'buyer', 'Common', '1', 'A', 'Street', 'T', 'eref']]
                (vendors if duplicate_kind == 'vendor' else employees).append(
                    (vendors if duplicate_kind == 'vendor' else employees)[0][:])
                self.write(vendors, employees)
                with self.assertRaises(ValueError):
                    self.analyze(max_findings=1)

    def test_distinct_ids_with_shared_account_remain_distinct_records(self):
        self.write([['v1', 'One', '1', 'A', 'Street A', 'T1', 'vref'],
                    ['v2', 'Two', '1', 'A', 'Street B', 'T2', 'vref']],
                   [['e', 'buyer', 'Worker', '1', 'A', 'Street C', 'T3', 'eref']])
        self.assertEqual([f['vendor_id'] for f in self.overlaps(self.analyze())], ['v1', 'v2'])

    def test_required_ids_and_evidence_and_paired_bank_account(self):
        base_v = ['v', 'Vendor', '1', 'A', 'Street', 'T', 'vref']
        base_e = ['e', 'buyer', 'Worker', '2', 'B', 'Home', 'U', 'eref']
        for kind, index in [('v', 0), ('v', 2), ('v', 3), ('v', 6),
                            ('e', 0), ('e', 1), ('e', 3), ('e', 4), ('e', 7)]:
            with self.subTest(kind=kind, index=index):
                vendor, employee = base_v[:], base_e[:]
                (vendor if kind == 'v' else employee)[index] = ' '
                self.write([vendor], [employee])
                with self.assertRaises(ValueError):
                    self.analyze()

    def test_malformed_csv_wrong_headers_and_invalid_banks_fail(self):
        self.write([], [])
        for content in [','.join(VENDORS) + '\nv,a,1\n',
                        ','.join(VENDORS) + '\nv,"unterminated\n',
                        ','.join(reversed(VENDORS)) + '\n',
                        ','.join(VENDORS) + '\nv,N,x,A,Street,T,ref\n']:
            with self.subTest(content=content):
                self.vendors.write_text(content, encoding='utf-8')
                with self.assertRaises(ValueError):
                    self.analyze()

    def test_cap_signals_omitted_findings_but_not_exactly_full_result(self):
        self.write([['v', 'Common', '1', 'A', 'Street', 'T', 'vref']],
                   [[str(i), 'buyer', 'Common', '2', str(i), 'Other', str(i), 'eref']
                    for i in range(30)])
        capped = self.analyze(max_findings=2)
        self.assertEqual(len(capped['findings']), 2)
        self.assertTrue(capped['truncated'])
        self.assertEqual([f['employee_id'] for f in capped['findings']], ['0', '1'])
        self.assertFalse(self.analyze(max_findings=30)['truncated'])

    def test_vendor_gaps_share_result_cap_and_empty_inputs_are_valid(self):
        self.write([['v1', '', '', '', '', '', 'vref'], ['v2', '', '', '', '', '', 'vref']], [])
        report = self.analyze(max_findings=1)
        self.assertEqual(len(report['findings']), 1)
        self.assertTrue(report['truncated'])
        self.write([], [])
        self.assertEqual(self.analyze()['findings'], [])
        self.assertFalse(self.analyze()['truncated'])

    def test_invalid_caps_rejected(self):
        self.write([], [])
        for value in (0, -1, 1.5, True, '2', None):
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    self.analyze(max_findings=value)

    def test_vendor_accounts_include_unmatched_rows_from_same_snapshot(self):
        self.write([['v', 'Vendor', '001', '000A', 'Street', 'T', 'vref'],
                    ['v2', 'Other', '', '', 'Road', 'U', 'v2ref']], [])
        report = self.analyze()
        accounts = report['vendor_accounts']
        self.assertEqual([(r['vendor_id'], r['bank'], r['account']) for r in accounts],
                         [('v', '1', '000A'), ('v2', '', '')])
        self.assertEqual(accounts[0]['source_sha256'], report['sources'][0]['sha256'])
        self.assertEqual(accounts[0]['source_row'], 2)
        self.assertEqual(accounts[0]['evidence_ref'], 'vref')
        self.assertNotIn('tax_id', accounts[0])
