"""Adapt IBM account metadata into explicitly derived, sourced account roles."""

from copy import deepcopy

from .evidence import load_table
from .ingest import normalize_bank


FIELDS = ['Bank Name', 'Bank ID', 'Account Number', 'Entity ID', 'Entity Name']


def _classify(name):
    for prefix, role in [('Individual', 'person'), ('Corporation', 'business'),
                         ('Partnership', 'business'), ('Sole Proprietorship', 'business')]:
        if name.startswith(prefix + ' ') and name[len(prefix) + 1:].strip():
            return role, 'derived_from_ibm_synthetic_entity_name:' + prefix
    return 'unknown', 'derived_from_ibm_synthetic_entity_name:unrecognized'


def _check_entities(context):
    entities = {}
    for record in context.values():
        entity_id = record['entity_id']
        name, role = record['entity_name'], record['entity_type']
        previous = entities.get(entity_id)
        if previous is not None:
            old_name, old_role = previous
            if old_name and name and old_name != name:
                raise ValueError('Conflicting entity name for ' + entity_id)
            if old_role != 'unknown' and role != 'unknown' and old_role != role:
                raise ValueError('Conflicting entity type for ' + entity_id)
            name = name or old_name
            role = old_role if role == 'unknown' else role
        entities[entity_id] = (name, role)


def load_ibm_accounts(path):
    """Return context and the manifest of the exact bytes parsed.

    Synthetic name prefixes support only a derived role, not verified legal
    ownership, employment, or shell-company status. Preserve all identifiers
    exactly except the numeric bank's leading zeros.
    """
    rows, source = load_table(path, FIELDS)
    context = {}
    for row in rows:
        number = row['_source_row']
        for field in ['Bank ID', 'Account Number', 'Entity ID', 'Entity Name']:
            if not row[field].strip():
                raise ValueError('Missing {} at IBM account record {}'.format(field, number))
        bank = normalize_bank(row['Bank ID'])
        account = row['Account Number']
        key = (bank, account)
        if key in context:
            raise ValueError('Duplicate IBM bank/account at record {}'.format(number))
        role, basis = _classify(row['Entity Name'])
        reference = 'sha256:{}#record={}'.format(source['sha256'], number)
        context[key] = {
            'bank': bank, 'account': account, 'entity_id': row['Entity ID'],
            'entity_type': role, 'entity_name': row['Entity Name'],
            'employee_of': '', 'evidence_ref': reference,
            'evidence_refs': [reference], 'classification_basis': basis,
        }
    _check_entities(context)
    return context, source


def _references(record):
    references = list(record.get('evidence_refs', []))
    if record.get('evidence_ref'):
        references.append(record['evidence_ref'])
    return list(dict.fromkeys(references))


def merge_contexts(ibm_context, explicit_context):
    """Merge compatible assertions without changing either input mapping.

    An unknown role or blank descriptive name is missing knowledge, not a
    contradictory assertion. Explicit context may resolve it and add an
    employment relationship. Keep every evidence reference after enrichment.
    """
    merged = deepcopy(ibm_context)
    for key, explicit in explicit_context.items():
        if key not in merged:
            merged[key] = deepcopy(explicit)
            merged[key]['evidence_refs'] = _references(explicit)
            merged[key].setdefault('classification_basis', 'explicit_context')
            continue
        original = merged[key]
        if original['entity_id'] != explicit['entity_id']:
            raise ValueError('Conflicting entity ID for bank/account {!r}'.format(key))
        if (original['entity_name'] and explicit['entity_name']
                and original['entity_name'] != explicit['entity_name']):
            raise ValueError('Conflicting entity name for bank/account {!r}'.format(key))
        old_role, new_role = original['entity_type'], explicit['entity_type']
        if old_role != 'unknown' and new_role != 'unknown' and old_role != new_role:
            raise ValueError('Conflicting entity type for bank/account {!r}'.format(key))
        if (original.get('employee_of') and explicit.get('employee_of')
                and original['employee_of'] != explicit['employee_of']):
            raise ValueError('Conflicting employment for bank/account {!r}'.format(key))
        result = dict(original)
        result['entity_name'] = explicit['entity_name'] or original['entity_name']
        result['entity_type'] = old_role if new_role == 'unknown' else new_role
        result['employee_of'] = explicit.get('employee_of') or original.get('employee_of', '')
        result['evidence_ref'] = explicit['evidence_ref']
        result['evidence_refs'] = list(dict.fromkeys(_references(original) + _references(explicit)))
        if new_role != 'unknown':
            if original.get('classification_basis'):
                result['ibm_classification_basis'] = original['classification_basis']
            result['classification_basis'] = 'explicit_context_with_compatible_ibm_metadata'
        merged[key] = result
    _check_entities(merged)
    return merged
