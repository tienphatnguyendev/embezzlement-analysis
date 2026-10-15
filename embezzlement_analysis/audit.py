"""Independent, streaming IBM HI-Small audit. Never selects investigation leads.

Run: python3 -m embezzlement_analysis.audit --input-dir data/raw/full-hi-small
"""

import argparse
import csv
import hashlib
import json
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path


ACCOUNT_HEADER = ['Bank Name', 'Bank ID', 'Account Number', 'Entity ID', 'Entity Name']
TX_HEADER = ['Timestamp', 'From Bank', 'Account', 'To Bank', 'Account',
             'Amount Received', 'Receiving Currency', 'Amount Paid', 'Payment Currency',
             'Payment Format', 'Is Laundering']
KAGGLE = 'https://www.kaggle.com/datasets/ealtman2019/ibm-transactions-for-anti-money-laundering-aml'
PAPER = 'https://arxiv.org/html/2306.16424v3'


def bank(value):
    if not value or not value.isascii() or not value.isdigit():
        raise ValueError('Invalid numeric bank ID: {!r}'.format(value))
    return value.lstrip('0') or '0'


def role(name):
    for prefix, kind in [('Individual ', 'person'), ('Corporation ', 'business'),
                         ('Partnership ', 'business'), ('Sole Proprietorship ', 'business')]:
        if name.startswith(prefix) and name[len(prefix):].strip():
            return kind
    return 'unknown'


def table(path, header):
    with Path(path).open(encoding='utf-8-sig', newline='') as stream:
        reader = csv.reader(stream, strict=True)
        if next(reader, None) != header:
            raise ValueError('Unexpected header: ' + str(path))
        for number, row in enumerate(reader, 2):
            if len(row) != len(header):
                raise ValueError('{} record {} has wrong field count'.format(path, number))
            yield number, row


def fingerprint(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(chunk)
    info = Path(path).stat()
    return {'file_name': Path(path).name, 'bytes': info.st_size,
            'sha256': digest.hexdigest(), 'mtime_ns': info.st_mtime_ns}


def audit_accounts(path):
    mapping, entity_names, bank_names = {}, {}, {}
    conflicts, entity_conflicts, bank_conflicts = set(), set(), set()
    names, roles, unknown_names = Counter(), Counter(), Counter()
    duplicates, conflicting_rows, empty_identity_rows = 0, 0, 0
    examples = []
    count = 0
    for number, row in table(path, ACCOUNT_HEADER):
        count += 1
        bank_name, bank_id, account, entity_id, name = row
        normalized = bank(bank_id)
        key, identity = (normalized, account), (entity_id, name)
        if not account.strip() or not entity_id.strip() or not name.strip():
            empty_identity_rows += 1
        kind = role(name)
        roles[kind] += 1
        names[name.split(' #', 1)[0] if ' #' in name else kind] += 1
        if kind == 'unknown':
            unknown_names[name] += 1
        if key in mapping:
            if mapping[key] == identity:
                duplicates += 1
            else:
                conflicting_rows += 1
                conflicts.add(key)
                if len(examples) < 20:
                    examples.append({'record': number, 'bank': normalized, 'account': account,
                                     'first_identity': mapping[key], 'other_identity': identity})
        else:
            mapping[key] = identity
        if entity_id in entity_names and entity_names[entity_id] != name:
            entity_conflicts.add(entity_id)
        else:
            entity_names[entity_id] = name
        if normalized in bank_names and bank_names[normalized] != bank_name:
            bank_conflicts.add(normalized)
        else:
            bank_names[normalized] = bank_name
    report = {
        'rows': count, 'unique_account_keys': len(mapping), 'unique_entities': len(entity_names),
        'unique_banks': len(bank_names), 'row_role_counts_derived_from_name': dict(roles),
        'entity_role_counts_derived_from_first_name': dict(Counter(role(x) for x in entity_names.values())),
        'synthetic_name_categories': dict(names), 'unknown_name_examples': unknown_names.most_common(20),
        'identical_duplicate_key_rows': duplicates, 'conflicting_duplicate_key_rows': conflicting_rows,
        'conflicting_account_keys': len(conflicts), 'conflict_examples': examples,
        'entity_ids_with_conflicting_names': len(entity_conflicts),
        'entity_conflict_examples': sorted(entity_conflicts)[:20],
        'bank_ids_with_conflicting_names': len(bank_conflicts),
        'empty_identity_rows': empty_identity_rows,
        'strict_accounts_adapter_would_reject': bool(duplicates or conflicting_rows or entity_conflicts or empty_identity_rows),
        'classification_limit': 'Roles are derived from synthetic names; employment and shell status are not supplied.',
    }
    return report, mapping, conflicts


def audit_patterns(path):
    types, labels = Counter(), Counter()
    signatures, errors = set(), []
    active, attempts, rows, duplicates = None, 0, 0, 0
    with Path(path).open(encoding='utf-8-sig') as stream:
        for line_number, line in enumerate(stream, 1):
            line = line.rstrip('\r\n')
            if not line:
                continue
            if line.startswith('BEGIN LAUNDERING ATTEMPT - '):
                if active is not None:
                    errors.append('Nested BEGIN at line {}'.format(line_number))
                active = line.split(' - ', 1)[1].split(':', 1)[0].strip()
                types[active] += 1
                attempts += 1
            elif line.startswith('END LAUNDERING ATTEMPT - '):
                ending = line.split(' - ', 1)[1].strip()
                if active != ending:
                    errors.append('Mismatched END at line {}'.format(line_number))
                active = None
            else:
                fields = next(csv.reader([line], strict=True))
                if len(fields) != len(TX_HEADER):
                    errors.append('Invalid transaction at line {}'.format(line_number))
                    continue
                if active is None:
                    errors.append('Transaction outside attempt at line {}'.format(line_number))
                signature = tuple(fields)
                duplicates += signature in signatures
                signatures.add(signature)
                labels[fields[10]] += 1
                rows += 1
    if active is not None:
        errors.append('Unclosed final attempt')
    return {'attempts': attempts, 'attempt_types': dict(types), 'transaction_rows': rows,
            'unique_transaction_signatures': len(signatures), 'duplicate_transaction_rows': duplicates,
            'label_counts': dict(labels), 'structural_errors': errors,
            'scope': 'Pattern membership is laundering evaluation metadata, not embezzlement truth.'}, signatures


def audit_transactions(path, accounts, conflicts, main_period_end, pattern_signatures=None):
    days = defaultdict(Counter)
    labels, paid_currencies, received_currencies, formats = Counter(), Counter(), Counter(), Counter()
    endpoint_coverage, endpoint_roles, unknown_examples = Counter(), Counter(), Counter()
    seen_accounts, unseen_patterns = set(), set(pattern_signatures or ())
    count, time_reversals, self_transfers, different_currencies, pattern_matches = 0, 0, 0, 0, 0
    first, last, previous = None, None, None
    for number, row in table(path, TX_HEADER):
        count += 1
        timestamp, label = row[0].replace('/', '-'), row[10]
        if label not in ('0', '1'):
            raise ValueError('Non-binary label at CSV record {}'.format(number))
        if len(timestamp) != 16:
            raise ValueError('Unexpected timestamp at CSV record {}'.format(number))
        first, last = min(first or timestamp, timestamp), max(last or timestamp, timestamp)
        if previous is not None and timestamp < previous:
            time_reversals += 1
        previous = timestamp
        days[timestamp[:10]][label] += 1
        labels[label] += 1
        paid_currencies[row[8]] += 1
        received_currencies[row[6]] += 1
        formats[row[9]] += 1
        different_currencies += row[8] != row[6]
        source, target = (bank(row[1]), row[2]), (bank(row[3]), row[4])
        self_transfers += source == target
        for endpoint in (source, target):
            seen_accounts.add(endpoint)
            if endpoint not in accounts:
                endpoint_coverage['missing_metadata'] += 1
                unknown_examples[endpoint] += 1
            elif endpoint in conflicts:
                endpoint_coverage['conflicting_metadata'] += 1
            else:
                endpoint_coverage['unambiguous_metadata'] += 1
                endpoint_roles[role(accounts[endpoint][1])] += 1
        if pattern_signatures is not None:
            signature = tuple(row)
            if signature in pattern_signatures:
                pattern_matches += 1
                unseen_patterns.discard(signature)
        if count % 1000000 == 0:
            print('Audited {:,} transaction rows'.format(count), flush=True)
    distinct_coverage = Counter('missing_metadata' if key not in accounts else
                                'conflicting_metadata' if key in conflicts else
                                'unambiguous_metadata' for key in seen_accounts)
    daily = [{'date': day, 'rows': sum(values.values()), 'label_0': values['0'],
              'label_1': values['1'], 'laundering_rate': values['1'] / sum(values.values())}
             for day, values in sorted(days.items())]
    tail = Counter()
    main = Counter()
    for day, counts in days.items():
        (tail if day > main_period_end else main).update(counts)
    return {
        'rows': count, 'label_counts': dict(labels),
        'laundering_rate': labels['1'] / count if count else None,
        'first_timestamp': first, 'last_timestamp': last,
        'daily_labels': daily, 'publisher_main_period_end': main_period_end,
        'through_publisher_main_window': {'rows': sum(main.values()), 'label_counts': dict(main)},
        'after_publisher_main_window': {'rows': sum(tail.values()), 'label_counts': dict(tail)},
        'payment_currency_counts': dict(paid_currencies), 'receiving_currency_counts': dict(received_currencies),
        'payment_format_counts': dict(formats), 'different_currency_rows': different_currencies,
        'self_transfer_rows': self_transfers, 'adjacent_timestamp_reversals': time_reversals,
        'unique_accounts_in_transactions': len(seen_accounts),
        'endpoint_occurrence_coverage': dict(endpoint_coverage),
        'unique_endpoint_coverage': dict(distinct_coverage),
        'endpoint_occurrence_roles_derived_from_name': dict(endpoint_roles),
        'missing_metadata_examples': [{'bank': key[0], 'account': key[1], 'occurrences': value}
                                      for key, value in unknown_examples.most_common(20)],
        'metadata_accounts_not_observed_in_transactions': len(set(accounts) - seen_accounts),
        'pattern_transaction_rows_found': pattern_matches,
        'pattern_unique_signatures_not_found': len(unseen_patterns),
        'duplicate_looking_transaction_count': None,
        'duplicate_count_note': 'Not computed: duplicate-looking transfers remain separate records; no expensive full-file grouping required.',
        'amount_validation': 'Not repeated by this profiling audit; ingest_csv validates every amount before importing.',
    }


def write_notes(path, report):
    tx, account, patterns = report['transactions'], report['accounts'], report['patterns']
    tail = tx['after_publisher_main_window']
    tail_comparison = ('The downloaded data contradicts that statement: both label values occur after '
                       'September 10. The elevated tail rate is not a perfect date-based classifier.'
                       if tail['label_counts'].get('0', 0) else
                       'No label-0 rows occur in the measured tail; check its size before interpreting this result.')
    daily = '\n'.join('| {} | {:,} | {:,} | {:,} |'.format(r['date'], r['rows'], r['label_0'], r['label_1'])
                      for r in tx['daily_labels'])
    text = '''# IBM HI-Small independent audit

The streamed files contain **{rows:,} transactions**, including **{laundering:,} laundering labels**.
These are laundering labels, not confirmed embezzlement cases. No label was used to select investigation leads.

The [publisher dataset page]({kaggle}) describes September 1–10, 2022 as the main activity period. This audit uses **2022-09-10** as that published boundary; it does not infer it from labels. The publisher also states that later transactions are all laundering. The measured tail has **{tail_rows:,} rows** and labels **{tail_labels}**: **{tail_positive:,}/{tail_rows:,} = {tail_rate:.2%} laundering, versus the publisher's 100% claim**. **{tail_comparison}** Temporal label artifacts cannot validate an embezzlement detector. The exact publisher description is preserved at `data/raw/full-hi-small/publisher-description.json`.

## Independent measurements

- Account metadata: {account_rows:,} rows, {account_keys:,} normalized bank/account keys, {entities:,} entity IDs.
- Account roles derived from synthetic names: `{roles}`. Unknown names are retained rather than forced into business/person classes. A person-targeted scan examines only a small portion of this metadata.
- Duplicate keys: {duplicates:,} repeated rows with the same initial identity; {conflicting:,} rows conflicting with the initial identity. The audit reports these rather than silently dropping or rejecting the source.
- Strict account adapter would reject: **{reject}**.
- Transaction endpoint join coverage: `{coverage}`. Each payment has two endpoint occurrences.
- Pattern metadata: {attempts:,} attempts, {pattern_rows:,} transaction rows, {unmatched_patterns:,} distinct pattern signatures absent from the transaction file.

## Label/date distribution

| Date | Transactions | Label 0 | Label 1 |
| --- | ---: | ---: | ---: |
{daily}

## Evaluation boundaries

The [IBM paper]({paper}) describes synthetic illicit-money tracking, including embezzlement as one source of criminal income. It does not provide an embezzlement case label, victim-company identity, employee relationship, invoice validity, or shell-company truth in this transaction schema. Synthetic entity-name prefixes support only explicitly derived business/person roles. The pattern file covers specified laundering structures, not every laundering transaction.

Use chronological evaluation and features derived only from earlier observations. Evaluate the main activity window separately from the tail; report both populations rather than silently deleting tail records. Pattern membership, laundering labels, and label-derived account features must remain evaluation-only. Preserve graph/account IDs as linkage keys, not memorized target predictors. Candidate counts and overlaps with AML labels do not measure embezzlement precision or recall.

The JSON audit records full file SHA-256 fingerprints. This script reads the published CSVs independently of the repository importer/scanner, checks source size/modification time after the audit, and never changes input files. Amount validation remains the importer's responsibility. Reproduce with `python3 -m embezzlement_analysis.audit --input-dir data/raw/full-hi-small`. The [IBM repository](https://github.com/IBM/AML-Data) identifies the data license as CDLA-Sharing-1.0, distinct from its Apache-2.0 code license.
'''.format(rows=tx['rows'], laundering=tx['label_counts'].get('1', 0), kaggle=KAGGLE,
           tail_rows=tail['rows'], tail_labels=tail['label_counts'], tail_comparison=tail_comparison,
           tail_positive=tail['label_counts'].get('1', 0),
           tail_rate=tail['label_counts'].get('1', 0) / tail['rows'] if tail['rows'] else 0,
           account_rows=account['rows'],
           account_keys=account['unique_account_keys'], entities=account['unique_entities'],
           roles=account['row_role_counts_derived_from_name'],
           duplicates=account['identical_duplicate_key_rows'], conflicting=account['conflicting_duplicate_key_rows'],
           reject=account['strict_accounts_adapter_would_reject'], coverage=tx['endpoint_occurrence_coverage'],
           attempts=patterns['attempts'], pattern_rows=patterns['transaction_rows'],
           unmatched_patterns=tx['pattern_unique_signatures_not_found'], daily=daily, paper=PAPER)
    Path(path).write_text(text, encoding='utf-8')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input-dir', type=Path, default=Path('data/raw/full-hi-small'))
    parser.add_argument('--output', type=Path, default=Path('reports/hi-small-audit.json'))
    parser.add_argument('--notes', type=Path, default=Path('reports/hi-small-audit-notes.md'))
    args = parser.parse_args()
    files = {key: args.input_dir / name for key, name in [
        ('transactions', 'HI-Small_Trans.csv'), ('accounts', 'HI-Small_accounts.csv'),
        ('patterns', 'HI-Small_Patterns.txt')]}
    sources = {key: fingerprint(path) for key, path in files.items()}
    accounts, mapping, conflicts = audit_accounts(files['accounts'])
    patterns, signatures = audit_patterns(files['patterns'])
    transactions = audit_transactions(files['transactions'], mapping, conflicts, '2022-09-10', signatures)
    for key, path in files.items():
        info = path.stat()
        if info.st_size != sources[key]['bytes'] or info.st_mtime_ns != sources[key]['mtime_ns']:
            raise ValueError('Input changed during audit: ' + str(path))
    report = {'created_at': datetime.now(timezone.utc).isoformat(), 'sources': sources,
              'publisher_sources': [KAGGLE, PAPER, 'https://github.com/IBM/AML-Data'],
              'label_usage': 'Evaluation-only; no lead selection or embezzlement truth inferred.',
              'accounts': accounts, 'patterns': patterns, 'transactions': transactions}
    acquisition = args.input_dir / 'acquisition.json'
    if acquisition.exists():
        acquired = json.loads(acquisition.read_text())
        report['publisher_dataset_version'] = acquired.get('dataset', {}).get('currentVersionNumber')
        expected = {entry['file_name']: entry['sha256'] for entry in acquired.get('files', [])}
        report['source_hashes_match_acquisition_manifest'] = all(
            expected.get(source['file_name']) == source['sha256'] for source in sources.values())
    publisher_snapshot = args.input_dir / 'publisher-description.json'
    if publisher_snapshot.exists():
        report['publisher_description_snapshot'] = fingerprint(publisher_snapshot)
    report['publisher_tail_all_laundering_claim_consistent'] = not bool(
        transactions['after_publisher_main_window']['label_counts'].get('0', 0))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.notes.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
    write_notes(args.notes, report)
    print(json.dumps({'audit': str(args.output), 'notes': str(args.notes),
                      'transactions': transactions['rows'], 'account_rows': accounts['rows']}))


if __name__ == '__main__':
    main()
