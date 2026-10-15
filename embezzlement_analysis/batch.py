"""Stream a complete two-hop scan without using target labels for selection."""

import csv
import hashlib
import json
import os
import sqlite3
import tempfile
from fractions import Fraction
from pathlib import Path

from .accounts import FIELDS, _classify
from .ingest import normalize_bank
from .numeric import positive_bounded_decimal


_EDGE_FIELDS = ['id', 'source_sha256', 'source_row', 'timestamp', 'from_bank',
                'from_account', 'to_bank', 'to_account', 'amount_paid',
                'payment_currency', 'amount_received', 'receiving_currency', 'payment_format']


def _load_accounts(conn, path, snapshot):
    """Hash while copying, then stream exactly those captured bytes into SQLite."""
    digest = hashlib.sha256()
    with path.open('rb') as source, snapshot.open('xb') as target:
        for block in iter(lambda: source.read(1024 * 1024), b''):
            digest.update(block)
            target.write(block)
    conn.executescript('''
        CREATE TABLE account_roles (
            bank TEXT NOT NULL, account TEXT NOT NULL, entity_id TEXT NOT NULL,
            entity_type TEXT NOT NULL, entity_name TEXT NOT NULL, source_row INTEGER NOT NULL,
            PRIMARY KEY(bank,account)) WITHOUT ROWID;
        CREATE TABLE entities (
            entity_id TEXT PRIMARY KEY, entity_name TEXT NOT NULL,
            entity_type TEXT NOT NULL) WITHOUT ROWID;
        CREATE TABLE selected(first_id INTEGER NOT NULL, second_id INTEGER NOT NULL,
            PRIMARY KEY(first_id,second_id)) WITHOUT ROWID;
    ''')
    count = 0
    try:
        with snapshot.open('r', encoding='utf-8-sig', newline='') as file:
            reader = csv.reader(file, strict=True)
            if next(reader, None) != FIELDS:
                raise ValueError('IBM accounts header must be: ' + ','.join(FIELDS))
            for source_row, row in enumerate(reader, 2):
                if len(row) != len(FIELDS):
                    raise ValueError('Wrong IBM account field count at record ' + str(source_row))
                for index in [1, 2, 3, 4]:
                    if not row[index].strip():
                        raise ValueError('Missing IBM account identity at record ' + str(source_row))
                bank, account, entity_id, name = normalize_bank(row[1]), row[2], row[3], row[4]
                role, _ = _classify(name)
                prior = conn.execute('INSERT OR IGNORE INTO entities VALUES (?,?,?)',
                                     (entity_id, name, role))
                if prior.rowcount == 0:
                    previous = conn.execute('SELECT entity_name,entity_type FROM entities WHERE entity_id=?',
                                            (entity_id,)).fetchone()
                    if tuple(previous) != (name, role):
                        raise ValueError('Conflicting IBM entity metadata at record ' + str(source_row))
                try:
                    conn.execute('INSERT INTO account_roles VALUES (?,?,?,?,?,?)',
                                 (bank, account, entity_id, role, name, source_row))
                except sqlite3.IntegrityError:
                    raise ValueError('Duplicate IBM bank/account at record ' + str(source_row)) from None
                count += 1
    except (csv.Error, UnicodeError) as error:
        raise ValueError('Invalid IBM accounts UTF-8 CSV: ' + str(error)) from error
    conn.execute('CREATE INDEX account_roles_type ON account_roles(entity_type)')
    conn.commit()
    return {'file_name': path.name, 'sha256': digest.hexdigest(), 'row_count': count}


def scan_dataset(db_path, accounts_path, output_path, window_hours=72,
                 min_ratio='0.8', max_ratio='1.05', max_examples=20):
    """Scan every supplied business→business→person two-hop candidate.

    Labels are absent from the selection query and JSONL. Each hop advances
    time, the final timestamp falls inside the total window, adjacent currencies
    match, and the exact amount ratio falls inside inclusive configured bounds.
    Three distinct account identities and entity IDs are required. Same-owner
    shapes are counted separately after the amount filter. Derived IBM entity
    names do not establish legal ownership or employment.

    Account metadata, selected ID pairs, and distinct counts use scratch disk.
    Only max_examples candidate objects are retained in Python; every selected
    candidate is streamed to JSONL. No scan cap is applied. Output publication
    is atomic and refuses to overwrite any existing file. On failure no final
    JSONL is published, and the temporary output is removed. Positive decimal
    inputs use the shared <=38 digits, exponent >=-18, magnitude <1e38 bounds.
    """
    if isinstance(max_examples, bool) or not isinstance(max_examples, int) or max_examples < 0:
        raise ValueError('max_examples must be a nonnegative integer')
    hours = positive_bounded_decimal(window_hours, 'window_hours')
    lower_decimal = positive_bounded_decimal(min_ratio, 'min_ratio')
    upper_decimal = positive_bounded_decimal(max_ratio, 'max_ratio')
    if lower_decimal > upper_decimal:
        raise ValueError('min_ratio must not exceed max_ratio')
    lower, upper = Fraction(lower_decimal), Fraction(upper_decimal)
    # Stored timestamps have second precision. Flooring is exact for the <=
    # comparison; saturation covers every representable SQLite calendar date.
    seconds = Fraction(hours) * 3600
    seconds_floor = min(seconds.numerator // seconds.denominator, 315537897599)
    db_path, accounts_path, output_path = Path(db_path), Path(accounts_path), Path(output_path)
    if output_path.exists():
        raise FileExistsError(str(output_path))
    if not db_path.is_file():
        raise FileNotFoundError(str(db_path))
    output_path.parent.mkdir(parents=True, exist_ok=True)
    summary = {
        'candidate_count': 0, 'unique_first_edges': 0, 'unique_second_edges': 0,
        'full_coverage': False, 'truncated': False, 'examples': [],
        'parameters': {'window_hours': str(hours), 'min_ratio': str(lower_decimal),
                       'max_ratio': str(upper_decimal), 'max_examples': max_examples},
        'examined': {'time_currency_role_pairs': 0, 'ratio_rejected_pairs': 0,
                     'ratio_pass_pairs': 0, 'same_account_pairs': 0, 'same_entity_pairs': 0,
                     'ownership_excluded_pairs': 0},
        'limitations': [
            'Complete coverage refers to the supplied ledger and the configured two-hop rule, '
            'not all fraud patterns or transactions outside the supplied data.',
            'Business/person roles derive from IBM synthetic names; neither ownership, '
            'employment, shell status, authorization nor embezzlement is established.',
            'Paths can overlap and funds can be mixed. Candidate amounts must not be summed '
            'as losses or attributed proceeds.',
            'Missing or unknown account roles exclude those endpoints from role-based selection '
            'and are reported as coverage gaps.',
            'Laundering labels are counted only after candidate selection; they are not '
            'embezzlement ground truth and do not rank the examples.',
            'Timestamps use the source clock without an inferred timezone. Equal-time hops '
            'are excluded because their order is unknown.',
            'Account metadata is a supplied snapshot without ownership effective dates.',
        ],
    }
    with tempfile.TemporaryDirectory(prefix='.batch-scan-', dir=str(output_path.parent)) as directory:
        scratch = Path(directory)
        conn = sqlite3.connect(str(scratch / 'scan.sqlite'), uri=True)
        conn.row_factory = sqlite3.Row
        try:
            conn.execute('PRAGMA temp_store=FILE')
            conn.execute('PRAGMA cache_size=-32768')
            conn.execute('PRAGMA journal_mode=OFF')
            account_source = _load_accounts(conn, accounts_path, scratch / 'accounts.csv')
            conn.execute('ATTACH DATABASE ? AS ledger', (db_path.resolve().as_uri() + '?mode=ro',))
            # Keep coverage, selected paths and post-selection label counts on
            # the same ledger snapshot. Scratch remains the only writable DB.
            conn.execute('BEGIN')
            summary['sources'] = {'accounts': account_source, 'transactions': [
                dict(row) for row in conn.execute('SELECT sha256,file_name,row_count FROM ledger.sources ORDER BY sha256')]}
            coverage = conn.execute('''SELECT COUNT(*) AS transaction_count,
                COALESCE(SUM(a.account IS NULL),0) AS missing_sender_metadata,
                COALESCE(SUM(b.account IS NULL),0) AS missing_recipient_metadata,
                COALESCE(SUM(a.entity_type='unknown'),0) AS unknown_sender_role,
                COALESCE(SUM(b.entity_type='unknown'),0) AS unknown_recipient_role,
                COALESCE(SUM(a.entity_type='business' AND b.entity_type='business'),0)
                    AS business_business_first_edges
                FROM ledger.transactions AS t
                LEFT JOIN account_roles AS a ON a.bank=t.from_bank AND a.account=t.from_account
                LEFT JOIN account_roles AS b ON b.bank=t.to_bank AND b.account=t.to_account''').fetchone()
            summary['coverage'] = dict(coverage)
            summary['coverage']['account_count'] = account_source['row_count']
            summary['coverage']['account_roles'] = {
                row[0]: row[1] for row in conn.execute('SELECT entity_type,COUNT(*) FROM account_roles GROUP BY entity_type')}

            # Materialize only person-ending second edges before the indexed
            # hop join. This label-free role filter preserves every eligible
            # pair while avoiding repeated searches through business payments.
            onward_fields = ','.join('t.' + field for field in _EDGE_FIELDS)
            conn.execute('CREATE TABLE onward_person_edges AS SELECT ' + onward_fields + '''
                FROM ledger.transactions AS t
                JOIN account_roles AS recipient
                  ON recipient.bank=t.to_bank AND recipient.account=t.to_account
                WHERE recipient.entity_type='person' ''')
            conn.execute('''CREATE INDEX onward_person_sender_time
                ON onward_person_edges(from_bank,from_account,timestamp,id)''')
            summary['coverage']['onward_person_edge_count'] = conn.execute(
                'SELECT COUNT(*) FROM onward_person_edges').fetchone()[0]

            edge_columns = ','.join(alias + '.' + field + ' AS ' + alias + '_' + field
                                    for alias in ['e1', 'e2'] for field in _EDGE_FIELDS)
            metadata_columns = ','.join(alias + '.' + field + ' AS ' + alias + '_' + field
                                        for alias in ['a', 'b', 'c']
                                        for field in ['entity_id', 'entity_name', 'entity_type', 'source_row'])
            query = 'SELECT ' + edge_columns + ',' + metadata_columns + '''
                FROM ledger.transactions AS e1
                CROSS JOIN account_roles AS a
                CROSS JOIN account_roles AS b
                CROSS JOIN onward_person_edges AS e2 INDEXED BY onward_person_sender_time
                CROSS JOIN account_roles AS c
                WHERE a.bank=e1.from_bank AND a.account=e1.from_account AND a.entity_type='business'
                  AND b.bank=e1.to_bank AND b.account=e1.to_account AND b.entity_type='business'
                  AND e2.from_bank=e1.to_bank AND e2.from_account=e1.to_account
                  AND e2.timestamp>e1.timestamp
                  AND e2.timestamp<=COALESCE(strftime('%Y-%m-%dT%H:%M:%S', e1.timestamp, ?), '9999-12-31T23:59:59')
                  AND e2.payment_currency=e1.receiving_currency
                  AND c.bank=e2.to_bank AND c.account=e2.to_account AND c.entity_type='person'
                ORDER BY e1.id,e2.timestamp,e2.id'''
            args = ('+' + str(seconds_floor) + ' seconds',)
            summary['query_plan'] = [row[3] for row in conn.execute('EXPLAIN QUERY PLAN ' + query, args)]
            output_temp = scratch / 'candidates.jsonl'
            last_first_id, received = None, None
            output_hash = hashlib.sha256()
            output_bytes = 0
            with output_temp.open('xb') as output:
                for row in conn.execute(query, args):
                    summary['examined']['time_currency_role_pairs'] += 1
                    if row['e1_id'] != last_first_id:
                        received = Fraction(positive_bounded_decimal(row['e1_amount_received'], 'amount_received'))
                        last_first_id = row['e1_id']
                    paid = Fraction(positive_bounded_decimal(row['e2_amount_paid'], 'amount_paid'))
                    ratio = paid / received
                    if not lower <= ratio <= upper:
                        summary['examined']['ratio_rejected_pairs'] += 1
                        continue
                    summary['examined']['ratio_pass_pairs'] += 1
                    nodes = [(row['e1_from_bank'], row['e1_from_account']),
                             (row['e1_to_bank'], row['e1_to_account']),
                             (row['e2_to_bank'], row['e2_to_account'])]
                    entities = [row[alias + '_entity_id'] for alias in ['a', 'b', 'c']]
                    same_account, same_entity = len(set(nodes)) != 3, len(set(entities)) != 3
                    summary['examined']['same_account_pairs'] += int(same_account)
                    summary['examined']['same_entity_pairs'] += int(same_entity)
                    if same_account or same_entity:
                        summary['examined']['ownership_excluded_pairs'] += 1
                        continue
                    candidate = {'path': [{field: row[alias + '_' + field] for field in _EDGE_FIELDS}
                                          for alias in ['e1', 'e2']],
                                 'accounts': [{'bank': node[0], 'account': node[1],
                                               'entity_id': row[alias + '_entity_id'],
                                               'entity_name': row[alias + '_entity_name'],
                                               'entity_type': row[alias + '_entity_type'],
                                               'source_row': row[alias + '_source_row'],
                                               'source_sha256': account_source['sha256']}
                                              for node, alias in zip(nodes, ['a', 'b', 'c'])]}
                    encoded = (json.dumps(candidate, ensure_ascii=False, separators=(',', ':')) + '\n').encode('utf-8')
                    output.write(encoded)
                    output_hash.update(encoded)
                    output_bytes += len(encoded)
                    conn.execute('INSERT INTO selected VALUES (?,?)', (row['e1_id'], row['e2_id']))
                    summary['candidate_count'] += 1
                    if len(summary['examples']) < max_examples:
                        summary['examples'].append(candidate)
            unique = conn.execute('SELECT COUNT(DISTINCT first_id),COUNT(DISTINCT second_id) FROM selected').fetchone()
            summary['unique_first_edges'], summary['unique_second_edges'] = unique
            # All label access begins here, after IDs, JSONL, and examples are
            # fixed. The publisher's cutoff identifies a phase, never a label.
            cutoff = '2022-09-11T00:00:00'
            phase_counts = {'cutoff': cutoff}
            for phase in ['main_window', 'contains_tail']:
                phase_counts[phase] = {'candidate_count': 0, 'all_labeled': 0,
                                       'some_labeled': 0, 'none_labeled': 0}
            labels = conn.execute('''SELECT
                CASE WHEN t1.timestamp<? AND t2.timestamp<?
                    THEN 'main_window' ELSE 'contains_tail' END AS phase,
                COUNT(*) AS candidate_count,
                SUM(t1.is_laundering=1 AND t2.is_laundering=1) AS all_labeled,
                SUM(t1.is_laundering<>t2.is_laundering) AS some_labeled,
                SUM(t1.is_laundering=0 AND t2.is_laundering=0) AS none_labeled
                FROM selected AS s
                JOIN ledger.transactions AS t1 ON t1.id=s.first_id
                JOIN ledger.transactions AS t2 ON t2.id=s.second_id
                GROUP BY phase''', (cutoff, cutoff))
            for row in labels:
                values = dict(row)
                phase = values.pop('phase')
                phase_counts[phase] = values
            summary['phase_label_diagnostics'] = phase_counts
            summary['label_diagnostics'] = {
                key: phase_counts['main_window'][key] + phase_counts['contains_tail'][key]
                for key in ['all_labeled', 'some_labeled', 'none_labeled']}
            summary['selected_edge_diagnostics'] = dict(conn.execute('''
                WITH edges(id) AS (SELECT first_id FROM selected UNION SELECT second_id FROM selected)
                SELECT COUNT(*) AS total,
                    COALESCE(SUM(t.is_laundering=1),0) AS laundering,
                    COALESCE(SUM(t.is_laundering=0),0) AS not_laundering
                FROM edges JOIN ledger.transactions AS t ON t.id=edges.id''').fetchone())
            summary['ledger_label_diagnostics'] = dict(conn.execute('''
                SELECT COUNT(*) AS total,
                    COALESCE(SUM(is_laundering=1),0) AS laundering,
                    COALESCE(SUM(is_laundering=0),0) AS not_laundering
                FROM ledger.transactions''').fetchone())
            summary['candidate_output'] = {'file_name': output_path.name, 'path': str(output_path.resolve()),
                                            'sha256': output_hash.hexdigest(), 'bytes': output_bytes,
                                            'row_count': summary['candidate_count']}
            summary['full_coverage'] = True
            conn.rollback()
            # Hard-link publication is atomic and fails on a concurrent file
            # creation, unlike replace/rename operations that overwrite.
            os.link(str(output_temp), str(output_path))
        finally:
            conn.close()
    return summary
