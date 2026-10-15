"""Compare supplied vendor/employee snapshots; produce evidence-linked leads."""

from collections import defaultdict
from heapq import merge
from itertools import groupby

from .evidence import load_table
from .ingest import normalize_bank


VENDORS = ['vendor_id', 'name', 'bank', 'account', 'address', 'tax_id', 'evidence_ref']
EMPLOYEES = ['employee_id', 'employer_entity_id', 'name', 'bank', 'account',
             'address', 'tax_id', 'evidence_ref']
MATCH_FIELDS = ('bank_account', 'tax_id', 'address', 'name')


def _present(value):
    return bool(value.strip())


def _description(value):
    return ' '.join(value.casefold().split())


def _validate(rows, source, id_field):
    seen = set()
    for row in rows:
        location = '%s CSV record %s' % (source['file_name'], row['_source_row'])
        required = [id_field, 'evidence_ref']
        if id_field == 'employee_id':
            required.append('employer_entity_id')
        for field in required:
            if not _present(row[field]):
                raise ValueError('%s: %s must be nonempty' % (location, field))
        if row[id_field] in seen:
            raise ValueError('%s: duplicate %s %r' % (location, id_field, row[id_field]))
        seen.add(row[id_field])
        bank_set, account_set = _present(row['bank']), _present(row['account'])
        if bank_set != account_set:
            raise ValueError('%s: bank and account must both be set or both be blank' % location)
        if bank_set:
            try:
                normalize_bank(row['bank'])
            except ValueError as error:
                raise ValueError('%s: %s' % (location, error)) from error


def _keys(row):
    """Normalize descriptions and numeric bank IDs only; exclude blank values."""
    values = {}
    if _present(row['bank']):
        values['bank_account'] = (normalize_bank(row['bank']), row['account'])
    if _present(row['tax_id']):
        values['tax_id'] = row['tax_id']
    for field in ('address', 'name'):
        value = _description(row[field])
        if value:
            values[field] = value
    return values


def _reference(row, source):
    return {**{field: value for field, value in row.items() if field != '_source_row'},
            'source_row': row['_source_row'], 'source_sha256': source['sha256'],
            'source_file': source['file_name']}


def analyze_masters(vendors_path, employees_path, max_findings=1000):
    """Return deterministic findings from validated, hashed CSV snapshots.

    IDs, tax IDs and accounts compare exactly. Names/addresses use casefolding
    and collapsed whitespace, without fuzzy or punctuation matching. Account
    identity includes the bank. A match does not prove ownership or employment.

    Employee posting lists hold row indexes in source order. Merging at most
    four lists yields unique candidate pairs lazily, so common names do not
    materialize a Cartesian product. Validation always covers every input row.
    Findings follow vendor source order, with profile gaps before pair matches.
    Truncation is true only when at least one additional finding was omitted.
    """
    if type(max_findings) is not int or max_findings <= 0:
        raise ValueError('max_findings must be a positive integer')
    vendors, vendor_source = load_table(vendors_path, VENDORS)
    employees, employee_source = load_table(employees_path, EMPLOYEES)
    _validate(vendors, vendor_source, 'vendor_id')
    _validate(employees, employee_source, 'employee_id')

    indexes = {field: defaultdict(list) for field in MATCH_FIELDS}
    employee_keys = []
    for index, row in enumerate(employees):
        keys = _keys(row)
        employee_keys.append(keys)
        for field, value in keys.items():
            indexes[field][value].append(index)

    def candidates():
        for vendor in vendors:
            keys = _keys(vendor)
            vendor_ref = _reference(vendor, vendor_source)
            missing = [field for field in ('bank', 'address', 'tax_id')
                       if not _present(vendor[field])]
            if missing:
                yield {
                    'rule_id': 'incomplete_vendor_profile',
                    'vendor_id': vendor['vendor_id'], 'missing_fields': missing,
                    'vendor': vendor_ref,
                    'interpretation': 'These fields are absent from the supplied vendor snapshot; '
                                      'this does not establish that the vendor is fictitious.',
                }
            postings = [indexes[field].get(value, ()) for field, value in keys.items()]
            for index, _ in groupby(merge(*postings)):
                employee = employees[index]
                fields = [field for field in MATCH_FIELDS
                          if field in keys and employee_keys[index].get(field) == keys[field]]
                values = {field: ({'bank': keys[field][0], 'account': keys[field][1]}
                                  if field == 'bank_account' else keys[field]) for field in fields}
                yield {
                    'rule_id': 'vendor_employee_overlap',
                    'vendor_id': vendor['vendor_id'], 'employee_id': employee['employee_id'],
                    'employer_entity_id': employee['employer_entity_id'],
                    'matched_fields': fields, 'matched_values': values,
                    'specificity': 'weak' if fields == ['name'] else 'stronger',
                    'vendor': vendor_ref, 'employee': _reference(employee, employee_source),
                    'evidence_refs': {'vendor': vendor['evidence_ref'],
                                      'employee': employee['evidence_ref']},
                    'interpretation': 'Supplied records share comparison values. Verify identity, '
                                      'the relationship and legitimate explanations; no fraud verdict.',
                }

    findings = []
    truncated = False
    for finding in candidates():
        if len(findings) == max_findings:
            truncated = True
            break
        findings.append(finding)

    vendor_accounts = [
        {'vendor_id': row['vendor_id'],
         'bank': normalize_bank(row['bank']) if _present(row['bank']) else '',
         'account': row['account'], 'source_row': row['_source_row'],
         'source_sha256': vendor_source['sha256'], 'evidence_ref': row['evidence_ref']}
        for row in vendors
    ]
    return {
        'sources': [dict(vendor_source, table='vendors'), dict(employee_source, table='employees')],
        'findings': findings, 'truncated': truncated, 'vendor_accounts': vendor_accounts,
        'limitations': [
            'Matches describe supplied snapshots; these schemas have no effective dates and '
            'do not establish a historical relationship.',
            'Names and addresses use casefolding and whitespace collapse only; accounts and '
            'tax IDs remain exact. Missing fields never match.',
            'Name-only matches are weak. Other overlaps are more specific comparison signals, '
            'not verified ownership, employment, conflicts of interest or fraud.',
            'Shared service providers, addresses, accounts, or legitimate disclosed relationships '
            'can explain overlaps. Consider corroborating and exculpatory evidence.',
            'Missing supplied data and no findings do not demonstrate that underlying records '
            'or relationships do not exist. No loss amounts are calculated.',
            'Findings are ordered by vendor source row, profile gaps first, then employee source '
            'row; the cap limits output and is not a risk ranking.',
        ],
    }
