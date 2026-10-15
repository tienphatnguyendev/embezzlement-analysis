"""Attach explicitly sourced entity context; never infer guilt or shell status."""

import csv
import hashlib
import io
from pathlib import Path


FIELDS = ['bank', 'account', 'entity_id', 'entity_type', 'entity_name', 'employee_of', 'evidence_ref']


def load_context(path):
    return load_context_snapshot(path)[0]


def load_context_snapshot(path):
    """Hash and parse the same bytes, even if the file later changes."""
    raw = Path(path).read_bytes()
    records = {}
    entities = {}
    with io.StringIO(raw.decode('utf-8-sig'), newline='') as stream:
        reader = csv.DictReader(stream, strict=True)
        if reader.fieldnames != FIELDS:
            raise ValueError('Context header must be: ' + ','.join(FIELDS))
        for row_number, row in enumerate(reader, 2):
            if None in row or any(value is None for value in row.values()):
                raise ValueError('Invalid context field count at record %s' % row_number)
            if not all(row[key].strip() for key in ['bank', 'account', 'entity_id', 'entity_type', 'evidence_ref']):
                raise ValueError('Missing identity or evidence at context record %s' % row_number)
            if not row['bank'].isascii() or not row['bank'].isdigit():
                raise ValueError('Context bank must be a numeric IBM bank identifier')
            row['bank'] = str(int(row['bank']))
            if row['entity_type'] not in {'business', 'person', 'unknown'}:
                raise ValueError('Context entity_type must be business, person, or unknown')
            if row['employee_of'] and row['entity_type'] != 'person':
                raise ValueError('Only a person can have employee_of context')
            key = (row['bank'], row['account'])
            if key in records:
                raise ValueError('Duplicate context account at record %s' % row_number)
            entity = (row['entity_type'], row['entity_name'], row['employee_of'])
            if row['entity_id'] in entities and entities[row['entity_id']] != entity:
                raise ValueError('Conflicting context for entity ' + row['entity_id'])
            entities[row['entity_id']] = entity
            records[key] = row
    return records, {'file_name': Path(path).name,
                     'sha256': hashlib.sha256(raw).hexdigest(),
                     'account_count': len(records)}


def annotate_paths(paths, context):
    findings = []
    for path in paths:
        keys = [(path[0]['from_bank'], path[0]['from_account'])]
        keys += [(edge['to_bank'], edge['to_account']) for edge in path]
        accounts = [dict(context.get(key, {
            'bank': key[0], 'account': key[1], 'entity_id': None,
            'entity_name': None, 'entity_type': 'unknown',
            'employee_of': None, 'evidence_ref': None,
        })) for key in keys]
        signals = []
        origin, recipient = accounts[0], accounts[-1]
        if origin['entity_type'] == 'business' and recipient['entity_type'] == 'person':
            signals.append('business_to_person')
            if recipient['employee_of'] and recipient['employee_of'] == origin['entity_id']:
                signals.append('recipient_employee_of_origin')
        findings.append({'transactions': path, 'accounts': accounts, 'review_signals': signals})
    return findings
