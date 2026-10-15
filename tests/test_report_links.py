import unittest

from embezzlement_analysis.__main__ import path_vendor_links


class ReportLinkTests(unittest.TestCase):
    def test_links_only_same_bank_and_account_and_vendor_findings(self):
        paths = [{'accounts': [{'bank': '1', 'account': 'ORIGIN'}, {'bank': '2', 'account': '000A'}]}]
        masters = {'vendor_accounts': [{'vendor_id': 'V', 'bank': '2', 'account': '000A'},
                                       {'vendor_id': 'WRONG', 'bank': '3', 'account': '000A'}],
                   'findings': [{'vendor_id': 'V'}, {'vendor_id': 'OTHER'}]}
        invoices = {'findings': [{'details': {'vendor_id': 'V'}}, {'vendor_id': 'OTHER'}]}
        result = path_vendor_links(paths, masters, invoices)
        self.assertEqual(len(result['links']), 1)
        self.assertEqual(result['links'][0]['master_finding_indices'], [1])
        self.assertEqual(result['links'][0]['invoice_finding_indices'], [1])
        self.assertFalse(result['truncated'])

    def test_many_vendors_sharing_account_cannot_expand_report_without_limit(self):
        paths = [{'accounts': [{'bank': '1', 'account': 'ORIGIN'}, {'bank': '2', 'account': 'A'}]}]
        masters = {'vendor_accounts': [{'vendor_id': str(n), 'bank': '2', 'account': 'A'} for n in range(3)], 'findings': []}
        result = path_vendor_links(paths, masters, {'findings': []}, max_links=1)
        self.assertEqual(len(result['links']), 1)
        self.assertTrue(result['truncated'])
