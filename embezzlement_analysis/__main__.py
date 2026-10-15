"""Local import and review-oriented tracing commands."""

import argparse
import csv
from contextlib import closing
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
    add_trace_arguments(trace)
    trace.add_argument('--output', help='New JSON report path; existing files are never overwritten')
    masters = commands.add_parser('check-masters', help='Compare supplied vendor and employee master records')
    add_master_arguments(masters)
    add_check_arguments(masters)
    invoices = commands.add_parser('check-invoices', help='Check invoices against purchasing and receipt evidence')
    add_invoice_arguments(invoices)
    add_check_arguments(invoices)
    investigation = commands.add_parser('investigate', help='Combine payment paths, identity matches, and invoice checks')
    add_trace_arguments(investigation)
    add_master_arguments(investigation)
    add_invoice_arguments(investigation)
    add_check_arguments(investigation)
    scan = commands.add_parser('scan', help='Scan every business-business-person two-payment chain')
    scan.add_argument('--db', required=True)
    scan.add_argument('--ibm-accounts', required=True)
    scan.add_argument('--candidates', required=True, help='New JSONL file for all selected chains')
    scan.add_argument('--window-hours', type=float, default=72)
    scan.add_argument('--min-ratio', type=decimal_argument, default=Decimal('0.8'))
    scan.add_argument('--max-ratio', type=decimal_argument, default=Decimal('1.05'))
    scan.add_argument('--max-examples', type=int, default=20)
    scan.add_argument('--output', help='New JSON summary path')
    return parser


def add_trace_arguments(trace):
    trace.add_argument('--db', required=True)
    trace.add_argument('--bank', required=True)
    trace.add_argument('--account', required=True)
    trace.add_argument('--context', help='Optional evidence-backed account context CSV')
    trace.add_argument('--ibm-accounts', help='Optional publisher-format IBM account metadata CSV')
    trace.add_argument('--max-hops', type=int, default=3)
    trace.add_argument('--window-hours', type=float, default=72)
    trace.add_argument('--min-ratio', type=decimal_argument, default=Decimal('0.8'))
    trace.add_argument('--max-ratio', type=decimal_argument, default=Decimal('1.05'))
    trace.add_argument('--max-paths', type=int, default=1000)
    trace.add_argument('--max-expansions', type=int, default=50000)


def add_master_arguments(parser):
    parser.add_argument('--vendors', required=True)
    parser.add_argument('--employees', required=True)


def add_invoice_arguments(parser):
    parser.add_argument('--invoices', required=True)
    parser.add_argument('--purchase-orders', required=True)
    parser.add_argument('--receipts', required=True)


def add_check_arguments(parser):
    parser.add_argument('--max-findings', type=int, default=1000)
    parser.add_argument('--output', help='New JSON report path; existing files are never overwritten')


def build_report(args):
    from .analysis import trace_paths

    context, context_source = load_context_snapshot(args.context) if args.context else ({}, None)
    ibm_source = None
    if getattr(args, 'ibm_accounts', None):
        from .accounts import load_ibm_accounts, merge_contexts
        ibm_context, ibm_source = load_ibm_accounts(args.ibm_accounts)
        context = merge_contexts(ibm_context, context)
    result = trace_paths(args.db, args.bank, args.account,
                         max_hops=args.max_hops, window_hours=args.window_hours,
                         min_ratio=args.min_ratio, max_ratio=args.max_ratio,
                         max_paths=args.max_paths, max_expansions=args.max_expansions)
    findings = annotate_paths(result.pop('paths'), context)
    with closing(sqlite3.connect(Path(args.db).resolve().as_uri() + '?mode=ro', uri=True)) as connection:
        connection.row_factory = sqlite3.Row
        sources = [dict(row) for row in connection.execute('SELECT sha256, file_name, row_count FROM sources ORDER BY sha256')]
    return {
        'schema_version': '1', 'tool_version': __version__,
        'created_at': datetime.now(timezone.utc).isoformat(),
        'conclusion': 'Candidate paths for review; embezzlement is not established.',
        'sources': sources, 'context_source': context_source, 'ibm_accounts_source': ibm_source,
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


def master_checks(args):
    from .masters import analyze_masters
    return analyze_masters(args.vendors, args.employees, max_findings=args.max_findings)


def invoice_checks(args):
    from .procurement import analyze_procurement
    return analyze_procurement(args.invoices, args.purchase_orders, args.receipts,
                               max_findings=args.max_findings)


def path_vendor_links(paths, masters, invoices, max_links=1000):
    """Link review evidence by explicit vendor account and vendor identifiers."""
    vendors = {}
    master_indices, invoice_indices = {}, {}
    for i, finding in enumerate(masters['findings'], 1):
        master_indices.setdefault(finding.get('vendor_id'), []).append(i)
    for i, finding in enumerate(invoices['findings'], 1):
        vendor_id = finding.get('vendor_id', finding.get('details', {}).get('vendor_id'))
        invoice_indices.setdefault(vendor_id, []).append(i)
    for row in masters.get('vendor_accounts', []):
        if row['bank'] and row['account']:
            vendors.setdefault((row['bank'], row['account']), []).append(row)
    links = []
    for index, path in enumerate(paths, 1):
        for account in path['accounts'][1:]:
            for vendor in vendors.get((account['bank'], account['account']), []):
                if len(links) >= max_links:
                    return {'links': links, 'truncated': True}
                vendor_id = vendor['vendor_id']
                links.append({
                    'path_index': index, 'vendor_id': vendor_id,
                    'bank': account['bank'], 'account': account['account'],
                    'vendor_evidence': vendor,
                    'master_finding_indices': master_indices.get(vendor_id, []),
                    'invoice_finding_indices': invoice_indices.get(vendor_id, []),
                })
    return {'links': links, 'truncated': False}


def build_investigation(args):
    report = build_report(args)
    masters, invoices = master_checks(args), invoice_checks(args)
    report['analysis_type'] = 'combined_investigation'
    report['master_checks'], report['invoice_checks'] = masters, invoices
    links = path_vendor_links(report['findings'], masters, invoices, max_links=args.max_findings)
    report['path_vendor_links'] = links['links']
    report['path_vendor_links_truncated'] = links['truncated']
    report['path_search_truncated'] = report['truncated']
    report['truncated'] = any([report['truncated'], masters['truncated'], invoices['truncated'], links['truncated']])
    report['truncation_reasons'] = [name for name, incomplete in [
        ('path_search', report['path_search_truncated']),
        ('master_checks', masters['truncated']), ('invoice_checks', invoices['truncated']),
        ('path_vendor_links', links['truncated'])] if incomplete]
    report['limitations'] = [item for item in report['limitations'] if 'invoices, and approval controls' not in item]
    report['limitations'].append('Split or merged funds and balance allocation are not analyzed. Procurement evidence is checked separately and linked by vendor ID.')
    report['limitations'].append('Master records describe the supplied snapshot; historical relationship dates are not established.')
    return report


def build_checks_report(args):
    result = master_checks(args) if args.command == 'check-masters' else invoice_checks(args)
    return {'schema_version': '1', 'tool_version': __version__,
            'created_at': datetime.now(timezone.utc).isoformat(),
            'analysis_type': args.command,
            'conclusion': 'Evidence exceptions for review; embezzlement is not established.', **result}


def build_scan_report(args):
    from .batch import scan_dataset
    result = scan_dataset(args.db, args.ibm_accounts, args.candidates,
                          window_hours=args.window_hours, min_ratio=args.min_ratio,
                          max_ratio=args.max_ratio, max_examples=args.max_examples)
    return {'schema_version': '1', 'tool_version': __version__,
            'created_at': datetime.now(timezone.utc).isoformat(),
            'analysis_type': 'dataset_scan', **result}


def main(argv=None):
    parser = make_parser()
    args = parser.parse_args(argv)
    try:
        if args.command == 'ingest':
            Path(args.db).parent.mkdir(parents=True, exist_ok=True)
            result = ingest_csv(args.csv, args.db)
            print(json.dumps(result, indent=2))
        else:
            if args.output and Path(args.output).exists():
                raise FileExistsError('Report already exists: ' + args.output)
            if args.command == 'scan' and args.output and Path(args.output).resolve() == Path(args.candidates).resolve():
                raise ValueError('Summary and candidate output paths must differ')
            if args.command == 'investigate':
                result = build_investigation(args)
            elif args.command == 'trace':
                result = build_report(args)
            elif args.command == 'scan':
                result = build_scan_report(args)
            else:
                result = build_checks_report(args)
            payload = json.dumps(result, indent=2, ensure_ascii=False) + '\n'
            if args.output:
                target = Path(args.output)
                target.parent.mkdir(parents=True, exist_ok=True)
                with target.open('x', encoding='utf-8') as stream:
                    stream.write(payload)
                summary = {'report': str(target), 'finding_count': len(result.get('findings', [])),
                           'truncated': result['truncated']}
                if args.command in ('trace', 'investigate'):
                    summary['candidate_paths'] = len(result['findings'])
                if args.command == 'investigate':
                    summary['master_findings'] = len(result['master_checks']['findings'])
                    summary['invoice_findings'] = len(result['invoice_checks']['findings'])
                    summary['vendor_links'] = len(result['path_vendor_links'])
                    summary['finding_count'] += summary['master_findings'] + summary['invoice_findings']
                if args.command == 'scan':
                    summary['finding_count'] = result['candidate_count']
                    summary['candidates'] = args.candidates
                print(json.dumps(summary))
            else:
                print(payload, end='')
    except (ValueError, OSError, sqlite3.Error, csv.Error) as error:
        parser.exit(2, 'error: %s\n' % error)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
