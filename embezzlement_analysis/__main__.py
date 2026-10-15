"""Local import and review-oriented tracing commands."""

import argparse
import csv
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
import json
from pathlib import Path
import sqlite3

from . import __version__
from .context import annotate_paths, load_context_snapshot
from .ingest import ingest_csv


def decimal_argument(value):
    try:
        return Decimal(value)
    except InvalidOperation:
        raise argparse.ArgumentTypeError('expected a decimal number') from None


def make_parser():
    parser = argparse.ArgumentParser(description='Research candidate payment paths; does not establish embezzlement.')
    commands = parser.add_subparsers(dest='command', required=True)
    ingest = commands.add_parser('ingest', help='Validate and import an IBM-format transaction CSV')
    ingest.add_argument('csv')
    ingest.add_argument('--db', required=True)
    trace = commands.add_parser('trace', help='Find bounded time-ordered paths from one account')
    trace.add_argument('--db', required=True)
    trace.add_argument('--bank', required=True)
    trace.add_argument('--account', required=True)
    trace.add_argument('--context', help='Optional evidence-backed account context CSV')
    trace.add_argument('--max-hops', type=int, default=3)
    trace.add_argument('--window-hours', type=float, default=72)
    trace.add_argument('--min-ratio', type=decimal_argument, default=Decimal('0.8'))
    trace.add_argument('--max-ratio', type=decimal_argument, default=Decimal('1.05'))
    trace.add_argument('--max-paths', type=int, default=1000)
    trace.add_argument('--max-expansions', type=int, default=50000)
    trace.add_argument('--output', help='New JSON report path; existing files are never overwritten')
    return parser


def build_report(args):
    from .analysis import trace_paths

    context, context_source = load_context_snapshot(args.context) if args.context else ({}, None)
    result = trace_paths(args.db, args.bank, args.account,
                         max_hops=args.max_hops, window_hours=args.window_hours,
                         min_ratio=args.min_ratio, max_ratio=args.max_ratio,
                         max_paths=args.max_paths, max_expansions=args.max_expansions)
    findings = annotate_paths(result.pop('paths'), context)
    with sqlite3.connect(Path(args.db).resolve().as_uri() + '?mode=ro', uri=True) as connection:
        connection.row_factory = sqlite3.Row
        sources = [dict(row) for row in connection.execute('SELECT sha256, file_name, row_count FROM sources ORDER BY sha256')]
    return {
        'schema_version': '1', 'tool_version': __version__,
        'created_at': datetime.now(timezone.utc).isoformat(),
        'conclusion': 'Candidate paths for review; embezzlement is not established.',
        'sources': sources, 'context_source': context_source,
        **result, 'findings': findings,
        'limitations': [
            'Amounts and timing are screening heuristics, not proof that the same funds moved.',
            'Paths may overlap. Never sum them as recovered funds or losses.',
            'Unknown entity roles remain unknown. Shell-company status is not inferred.',
            'Missing onward transfers may reflect missing records, not absence of misconduct.',
            'IBM timestamps have no timezone and minute precision; equal-time hops are excluded.',
            'Split or merged flows, balance allocation, invoices, and approval controls are not analyzed.',
            'Source fingerprints support reproducibility; they do not constitute a full chain-of-custody process.',
        ],
    }


def main(argv=None):
    parser = make_parser()
    args = parser.parse_args(argv)
    try:
        if args.command == 'ingest':
            Path(args.db).parent.mkdir(parents=True, exist_ok=True)
            result = ingest_csv(args.csv, args.db)
            print(json.dumps(result, indent=2))
        else:
            result = build_report(args)
            payload = json.dumps(result, indent=2, ensure_ascii=False) + '\n'
            if args.output:
                target = Path(args.output)
                target.parent.mkdir(parents=True, exist_ok=True)
                with target.open('x', encoding='utf-8') as stream:
                    stream.write(payload)
                print(json.dumps({'report': str(target), 'candidate_paths': len(result['findings']),
                                  'truncated': result['truncated']}))
            else:
                print(payload, end='')
    except (ValueError, OSError, sqlite3.Error, csv.Error) as error:
        parser.exit(2, 'error: %s\n' % error)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
