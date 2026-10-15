"""Bounded temporal path search: candidate connections, never proof of theft.

The adjacent amount filter is a heuristic. It neither allocates commingled
funds nor identifies account ownership. Overlapping paths must not be summed.
"""

import math
import sqlite3
from datetime import datetime, timedelta
from decimal import Decimal
from fractions import Fraction
from pathlib import Path

from .numeric import positive_bounded_decimal as _positive_decimal


_COLUMNS = (
    'id,source_sha256,source_row,timestamp,from_bank,from_account,to_bank,'
    'to_account,amount_paid,payment_currency,amount_received,receiving_currency,'
    'payment_format'
)


def _integer(value, name, minimum, maximum=None):
    if isinstance(value, bool) or not isinstance(value, int) or value < minimum:
        raise ValueError(name + ' must be an integer at least ' + str(minimum))
    if maximum is not None and value > maximum:
        raise ValueError(name + ' must be at most ' + str(maximum))
    return value


def trace_paths(db_path, start_bank, start_account, max_hops=3, window_hours=72,
                min_ratio=Decimal('0.8'), max_ratio=Decimal('1.05'),
                max_paths=1000, max_expansions=50000):
    """Return simple, strictly time-ordered paths of two through six hops.

    An expansion is one row examined, including root edges and rejected rows.
    Reaching either cap conservatively marks the result incomplete, even when
    that row might happen to be the final eligible row. Queries use the
    ingestion-created sender/time index. The database is opened read-only.
    Amounts, ratios, and window_hours must be finite positive decimals with
    at most 38 coefficient digits, exponent >=-18, and magnitude <1e38.
    The time window must additionally fit the supported timedelta range.
    """
    max_hops = _integer(max_hops, 'max_hops', 2, 6)
    max_paths = _integer(max_paths, 'max_paths', 1)
    max_expansions = _integer(max_expansions, 'max_expansions', 1)
    lower = _positive_decimal(min_ratio, 'min_ratio')
    upper = _positive_decimal(max_ratio, 'max_ratio')
    if lower > upper:
        raise ValueError('min_ratio must not exceed max_ratio')
    hours_decimal = _positive_decimal(window_hours, 'window_hours')
    try:
        hours = float(hours_decimal)
        if not math.isfinite(hours):
            raise OverflowError
        window = timedelta(hours=hours)
        if window <= timedelta(0):
            raise OverflowError
    except (OverflowError, ValueError):
        raise ValueError('window_hours is outside the supported time range') from None
    if not isinstance(start_account, str) or not start_account.strip():
        raise ValueError('start_account must be a nonempty account identifier')
    if isinstance(start_bank, bool):
        raise ValueError('start_bank must be a numeric bank identifier')
    try:
        bank_text = str(start_bank).strip()
        bank = str(int(bank_text))
    except (ValueError, TypeError):
        raise ValueError('start_bank must be a numeric bank identifier') from None
    if int(bank) < 0:
        raise ValueError('start_bank must be nonnegative')

    result = {
        'paths': [], 'truncated': False, 'truncation_reason': None, 'expansions': 0,
        'parameters': {
            'start_bank': bank, 'start_account': start_account,
            'max_hops': max_hops, 'window_hours': hours,
            'min_ratio': str(lower), 'max_ratio': str(upper),
            'max_paths': max_paths, 'max_expansions': max_expansions,
        },
    }
    lower_fraction, upper_fraction = Fraction(lower), Fraction(upper)

    def stop(reason):
        if not result['truncated']:
            result['truncated'] = True
            result['truncation_reason'] = reason

    def visit(conn, node, path, seen, deadline=None):
        remaining = max_expansions - result['expansions']
        if remaining <= 0:
            stop('max_expansions')
            return
        sql = 'SELECT ' + _COLUMNS + ' FROM transactions WHERE from_bank=? AND from_account=?'
        args = [node[0], node[1]]
        if path:
            sql += ' AND timestamp>? AND timestamp<=?'
            args.extend([path[-1]['timestamp'], deadline])
        sql += ' ORDER BY timestamp,id LIMIT ?'
        args.append(remaining)
        cursor = conn.execute(sql, args)
        try:
            for row in cursor:
                result['expansions'] += 1
                edge = dict(row)
                target = (edge['to_bank'], edge['to_account'])
                accepted = target not in seen
                paid = _positive_decimal(edge['amount_paid'], 'amount_paid')
                _positive_decimal(edge['amount_received'], 'amount_received')
                if accepted and path:
                    previous = path[-1]
                    if edge['payment_currency'] != previous['receiving_currency']:
                        accepted = False
                    else:
                        received = _positive_decimal(previous['amount_received'], 'amount_received')
                        ratio = Fraction(paid) / Fraction(received)
                        accepted = lower_fraction <= ratio <= upper_fraction
                if accepted:
                    next_path = path + [edge]
                    if not path:
                        first_time = datetime.strptime(edge['timestamp'], '%Y-%m-%dT%H:%M:%S')
                        try:
                            next_deadline = (first_time + window).isoformat(timespec='seconds')
                        except OverflowError:
                            next_deadline = '9999-12-31T23:59:59'
                    else:
                        next_deadline = deadline
                    if len(next_path) >= 2:
                        result['paths'].append(next_path)
                        if len(result['paths']) >= max_paths:
                            stop('max_paths')
                    if result['expansions'] >= max_expansions:
                        stop('max_expansions')
                    if not result['truncated'] and len(next_path) < max_hops:
                        visit(conn, target, next_path, seen | {target}, next_deadline)
                if result['expansions'] >= max_expansions:
                    stop('max_expansions')
                if result['truncated']:
                    break
        finally:
            cursor.close()

    uri = Path(db_path).resolve().as_uri() + '?mode=ro'
    conn = sqlite3.connect(uri, uri=True)
    try:
        conn.row_factory = sqlite3.Row
        conn.execute('PRAGMA query_only=ON')
        # A read transaction gives all traversals one consistent database view.
        conn.execute('BEGIN')
        origin = (bank, start_account)
        exists = conn.execute(
            'SELECT 1 FROM transactions WHERE from_bank=? AND from_account=? LIMIT 1',
            origin).fetchone()
        if exists is None:
            raise ValueError('Origin has no outgoing transactions; verify bank and account identifiers')
        visit(conn, origin, [], {origin})
        return result
    finally:
        conn.close()
