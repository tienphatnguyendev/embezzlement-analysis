import csv
import hashlib
import tempfile
import unittest
from pathlib import Path

from embezzlement_analysis.accounts import load_ibm_accounts, merge_contexts
from embezzlement_analysis.context import load_context


FIELDS = ['Bank Name', 'Bank ID', 'Account Number', 'Entity ID', 'Entity Name']
ROOT = Path(__file__).resolve().parents[1]


class AccountsTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / 'accounts.csv'

    def write(self, rows, header=FIELDS):
        with self.path.open('w', encoding='utf-8', newline='') as stream:
            writer = csv.writer(stream)
            writer.writerow(header)
            writer.writerows(rows)

    def record(self, entity_type='person', entity_name='Individual Jane',
               entity_id='000E', evidence_ref='explicit:record', employee_of='employer'):
        return {'bank': '1', 'account': '000A', 'entity_id': entity_id,
                'entity_type': entity_type, 'entity_name': entity_name,
                'employee_of': employee_of, 'evidence_ref': evidence_ref}

    def test_normalizes_only_bank_ids_and_preserves_composite_identity(self):
        self.write([['Bank', '001', '000A', '000E', 'Individual Jane'],
                    ['Other Bank', '002', '000A', '000F', 'Individual Sam']])
        context, _ = load_ibm_accounts(self.path)
        self.assertEqual(set(context), {('1', '000A'), ('2', '000A')})
        self.assertEqual(context[('1', '000A')]['entity_id'], '000E')

    def test_roles_are_derived_without_inventing_employee_or_shell_links(self):
        names = ['Individual Jane', 'Corporation #4', 'Partnership #5',
                 'Sole Proprietorship #6', 'Country #7', 'Individual',
                 'CorporationXYZ', 'Example Person']
        self.write([['Bank', '1', str(i), str(i), name] for i, name in enumerate(names)])
        context, _ = load_ibm_accounts(self.path)
        self.assertEqual([context[('1', str(i))]['entity_type'] for i in range(len(names))],
                         ['person', 'business', 'business', 'business', 'unknown',
                          'unknown', 'unknown', 'unknown'])
        for record in context.values():
            self.assertFalse(record['employee_of'])
            self.assertNotIn('is_shell', record)
            self.assertIn('derived', record['classification_basis'])

    def test_evidence_references_hash_exact_snapshot_and_csv_record(self):
        self.write([['Bank\nbranch', '1', '000A', '000E', 'Individual Jane'],
                    ['Bank', '2', 'B', 'E2', 'Corporation #2']])
        original = self.path.read_bytes()
        context, source = load_ibm_accounts(self.path)
        self.path.write_text('changed after import')
        digest = hashlib.sha256(original).hexdigest()
        self.assertEqual(source['sha256'], digest)
        self.assertEqual(source['file_name'], 'accounts.csv')
        self.assertEqual(source['row_count'], 2)
        self.assertEqual(context[('1', '000A')]['evidence_ref'], 'sha256:' + digest + '#record=2')
        self.assertEqual(context[('2', 'B')]['evidence_ref'], 'sha256:' + digest + '#record=3')

    def test_duplicate_normalized_account_is_rejected(self):
        self.write([['Bank', '01', 'A', 'E', 'Individual Jane'],
                    ['Bank', '1', 'A', 'E', 'Individual Jane']])
        with self.assertRaises(ValueError):
            load_ibm_accounts(self.path)

    def test_same_entity_with_conflicting_names_is_rejected(self):
        self.write([['Bank', '1', 'A', 'E', 'Individual Jane'],
                    ['Bank', '1', 'B', 'E', 'Corporation #1']])
        with self.assertRaises(ValueError):
            load_ibm_accounts(self.path)

    def test_missing_identity_or_nonnumeric_bank_is_rejected(self):
        for column, value in [(1, 'bank'), (2, ''), (3, ''), (4, '')]:
            row = ['Bank', '1', 'A', 'E', 'Individual Jane']
            row[column] = value
            self.write([row])
            with self.subTest(column=column), self.assertRaises(ValueError):
                load_ibm_accounts(self.path)

    def test_exact_header_is_required(self):
        self.write([], ['Bank Name', 'Bank ID', 'Account', 'Entity ID', 'Entity Name'])
        with self.assertRaises(ValueError):
            load_ibm_accounts(self.path)

    def test_whitespace_in_identifiers_is_not_silently_stripped(self):
        self.write([['Bank', '1', ' A ', ' E ', 'Individual Jane']])
        context, _ = load_ibm_accounts(self.path)
        self.assertIn(('1', ' A '), context)
        self.assertEqual(context[('1', ' A ')]['entity_id'], ' E ')

    def test_merge_enriches_employment_and_retains_both_evidence_sources(self):
        self.write([['Bank', '1', '000A', '000E', 'Individual Jane']])
        ibm, _ = load_ibm_accounts(self.path)
        explicit = {('1', '000A'): self.record()}
        merged = merge_contexts(ibm, explicit)
        result = merged[('1', '000A')]
        self.assertEqual(result['employee_of'], 'employer')
        self.assertEqual(set(result['evidence_refs']),
                         {ibm[('1', '000A')]['evidence_ref'], 'explicit:record'})
        self.assertFalse(ibm[('1', '000A')]['employee_of'])
        self.assertNotIn('evidence_refs', explicit[('1', '000A')])

    def test_merge_rejects_conflicting_id_name_or_known_type(self):
        self.write([['Bank', '1', '000A', '000E', 'Individual Jane']])
        ibm, _ = load_ibm_accounts(self.path)
        for kwargs in [dict(entity_id='other'), dict(entity_name='Individual Other'),
                       dict(entity_type='business', employee_of='')]:
            with self.subTest(kwargs=kwargs), self.assertRaises(ValueError):
                merge_contexts(ibm, {('1', '000A'): self.record(**kwargs)})

    def test_explicit_context_can_resolve_unknown_but_cannot_erase_known_type(self):
        ibm = {('1', '000A'): self.record(entity_type='unknown', employee_of='')}
        result = merge_contexts(ibm, {('1', '000A'): self.record()})
        self.assertEqual(result[('1', '000A')]['entity_type'], 'person')
        self.assertIn('explicit', result[('1', '000A')]['classification_basis'])
        known = {('1', '000A'): self.record(employee_of='')}
        unknown = {('1', '000A'): self.record(entity_type='unknown', employee_of='')}
        self.assertEqual(merge_contexts(known, unknown)[('1', '000A')]['entity_type'], 'person')

    def test_authored_ibm_demo_merges_with_existing_explicit_context(self):
        ibm, _ = load_ibm_accounts(ROOT / 'examples' / 'ibm_accounts.csv')
        explicit = load_context(ROOT / 'examples' / 'demo_context.csv')
        merged = merge_contexts(ibm, explicit)
        self.assertEqual(merged[('3', 'PERSONAL')]['employee_of'], 'buyer')
        self.assertEqual(merged[('1', 'VICTIM')]['entity_type'], 'business')

    def test_merge_retains_nonoverlapping_accounts_without_sharing_mutable_records(self):
        ibm = {('1', '000A'): self.record(employee_of='')}
        explicit_record = self.record(entity_id='other')
        explicit_record['account'] = 'B'
        explicit = {('1', 'B'): explicit_record}
        merged = merge_contexts(ibm, explicit)
        self.assertEqual(set(merged), {('1', '000A'), ('1', 'B')})
        merged[('1', 'B')]['entity_name'] = 'Changed'
        self.assertEqual(explicit[('1', 'B')]['entity_name'], 'Individual Jane')

    def test_merge_rejects_entity_conflict_even_across_different_accounts(self):
        ibm = {('1', '000A'): self.record(employee_of='')}
        explicit_record = self.record(entity_name='Individual Different')
        explicit_record['account'] = 'B'
        with self.assertRaises(ValueError):
            merge_contexts(ibm, {('1', 'B'): explicit_record})

    def test_blank_optional_explicit_name_preserves_known_ibm_name(self):
        ibm = {('1', '000A'): self.record(employee_of='')}
        merged = merge_contexts(ibm, {('1', '000A'): self.record(entity_name='')})
        self.assertEqual(merged[('1', '000A')]['entity_name'], 'Individual Jane')


if __name__ == '__main__':
    unittest.main()
