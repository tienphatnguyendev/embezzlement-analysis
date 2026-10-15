import json
import sqlite3
import tempfile
import unittest
from decimal import Decimal
from pathlib import Path

from embezzlement_analysis.analysis import _positive_decimal, trace_paths


class TracePathsTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.db = Path(self.temp.name) / 'case.sqlite'
        with sqlite3.connect(self.db) as conn:
            conn.executescript('''
                CREATE TABLE sources(sha256 TEXT, file_name TEXT, row_count INTEGER);
                CREATE TABLE transactions(
                    id INTEGER PRIMARY KEY, source_sha256 TEXT, source_row INTEGER,
                    timestamp TEXT, from_bank TEXT, from_account TEXT,
                    to_bank TEXT, to_account TEXT, amount_paid TEXT,
                    payment_currency TEXT, amount_received TEXT,
                    receiving_currency TEXT, payment_format TEXT, is_laundering INTEGER);
                CREATE INDEX sender_time ON transactions(from_bank,from_account,timestamp,id);
                INSERT INTO sources VALUES ('hash','fixture.csv',0);
            ''')

    def edge(self, sender, recipient, hour, amount='100', received=None,
             currency='USD', receiving=None, label=0, bank='1', to_bank='1'):
        with sqlite3.connect(self.db) as conn:
            source_row = conn.execute('SELECT count(*) + 2 FROM transactions').fetchone()[0]
            return conn.execute('''INSERT INTO transactions VALUES
                (NULL,?,?,?,?,?,?,?,?,?,?,?,?,?)''',
                ('hash', source_row, '2024-01-%02dT%02d:00:00' % (1 + hour // 24, hour % 24),
                 bank, sender, to_bank, recipient, str(amount), currency,
                 str(received if received is not None else amount), receiving or currency,
                 'ACH', label)).lastrowid

    def trace(self, **kwargs):
        return trace_paths(self.db, '001', 'company', **kwargs)

    @staticmethod
    def ids(result):
        return [[row['id'] for row in path] for path in result['paths']]

    def test_emits_two_and_three_hop_prefixes_with_provenance_without_labels(self):
        self.edge('company', 'middle', 0)
        self.edge('middle', 'person', 1)
        self.edge('person', 'final', 2)
        result = self.trace()
        self.assertEqual(self.ids(result), [[1, 2], [1, 2, 3]])
        self.assertFalse(result['truncated'])
        self.assertEqual(result['paths'][0][0]['source_sha256'], 'hash')
        self.assertNotIn('is_laundering', result['paths'][0][0])
        json.dumps(result)

    def test_requires_strict_time_order_and_total_not_per_edge_window(self):
        self.edge('company', 'middle', 2)
        self.edge('middle', 'before', 1)
        self.edge('middle', 'same', 2)
        self.edge('middle', 'next', 48)
        self.edge('next', 'late', 75)
        self.assertEqual(self.ids(self.trace(window_hours=72)), [[1, 4]])

    def test_compares_payment_to_previous_received_amount_in_same_currency(self):
        self.edge('company', 'middle', 0, '100', received='2400000', receiving='VND')
        self.edge('middle', 'wrong_currency', 1, '2400000', currency='USD')
        self.edge('middle', 'too_small', 2, '100', currency='VND')
        self.edge('middle', 'person', 3, '2000000', currency='VND')
        self.assertEqual(self.ids(self.trace()), [[1, 4]])

    def test_ratio_bounds_are_inclusive_and_decimal_exact(self):
        self.edge('company', 'middle', 0, '0.10')
        for hour, amount in enumerate(['0.08', '0.105', '0.079999', '0.105001'], 1):
            self.edge('middle', 'person' + str(hour), hour, amount)
        self.assertEqual(self.ids(self.trace()), [[1, 2], [1, 3]])

    def test_excludes_cycles_and_self_transfers_but_distinguishes_bank_accounts(self):
        self.edge('company', 'company', 0)
        self.edge('company', 'middle', 1)
        self.edge('middle', 'middle', 2)
        self.edge('middle', 'company', 3)
        self.edge('middle', 'company', 4, to_bank='2')
        self.assertEqual(self.ids(self.trace()), [[2, 5]])

    def test_max_hops_excludes_longer_paths(self):
        self.edge('company', 'middle', 0)
        self.edge('middle', 'person', 1)
        self.edge('person', 'final', 2)
        self.assertEqual(self.ids(self.trace(max_hops=2)), [[1, 2]])

    def test_labels_do_not_change_selection_or_output(self):
        self.edge('company', 'middle', 0, label=1)
        self.edge('middle', 'person', 1)
        before = self.trace()
        with sqlite3.connect(self.db) as conn:
            conn.execute('UPDATE transactions SET is_laundering = 1 - is_laundering')
        self.assertEqual(before, self.trace())

    def test_identical_values_in_distinct_rows_are_not_silently_deduplicated(self):
        self.edge('company', 'middle', 0)
        self.edge('company', 'middle', 0)
        self.edge('middle', 'person', 1)
        self.assertEqual(self.ids(self.trace()), [[1, 3], [2, 3]])

    def test_path_limit_reports_incomplete_search(self):
        self.edge('company', 'middle', 0)
        self.edge('middle', 'person', 1)
        self.edge('middle', 'other', 2)
        result = self.trace(max_paths=1)
        self.assertEqual(self.ids(result), [[1, 2]])
        self.assertTrue(result['truncated'])
        self.assertEqual(result['truncation_reason'], 'max_paths')

    def test_expansion_limit_counts_rejected_roots_and_stops(self):
        for hour in range(10):
            self.edge('company', 'company', hour)
        result = self.trace(max_expansions=3)
        self.assertEqual(result['paths'], [])
        self.assertEqual(result['expansions'], 3)
        self.assertTrue(result['truncated'])
        self.assertEqual(result['truncation_reason'], 'max_expansions')

    def test_single_visible_edge_is_not_an_invented_path(self):
        self.edge('company', 'middle', 0)
        self.assertEqual(self.trace()['paths'], [])

    def test_accounts_preserve_leading_zeroes(self):
        self.edge('company', '001', 0)
        self.edge('1', 'wrong', 1)
        self.edge('001', 'person', 2)
        self.assertEqual(self.ids(self.trace()), [[1, 3]])

    def test_mixed_funds_produce_candidates_without_allocating_or_summing(self):
        self.edge('company', 'middle', 0)
        self.edge('unrelated', 'middle', 1)
        self.edge('middle', 'person_a', 2)
        self.edge('middle', 'person_b', 3)
        result = self.trace()
        self.assertEqual(self.ids(result), [[1, 3], [1, 4]])
        self.assertNotIn('total_loss', result)
        self.assertNotIn('attributed_amount', result['paths'][0][1])

    def test_expansion_limit_is_global_across_roots_and_children(self):
        self.edge('company', 'middle', 0)
        self.edge('middle', 'person', 1)
        self.edge('middle', 'other', 2)
        result = self.trace(max_expansions=2)
        self.assertEqual(self.ids(result), [[1, 2]])
        self.assertEqual(result['expansions'], 2)
        self.assertTrue(result['truncated'])

    def test_absent_or_empty_origin_raises(self):
        with self.assertRaises(ValueError):
            self.trace()
        with self.assertRaises(ValueError):
            trace_paths(self.db, '1', '')

    def test_invalid_parameters_raise(self):
        self.edge('company', 'middle', 0)
        for kwargs in [dict(max_hops=1), dict(max_hops=7), dict(max_hops=2.5),
                       dict(window_hours=0), dict(window_hours=float('inf')),
                       dict(min_ratio=Decimal('NaN')), dict(min_ratio=0),
                       dict(min_ratio=2, max_ratio=1), dict(max_paths=0),
                       dict(max_expansions=-1), dict(max_paths=True)]:
            with self.subTest(kwargs=kwargs), self.assertRaises(ValueError):
                self.trace(**kwargs)

    def test_rejects_unbounded_decimals_before_fraction_conversion(self):
        # Call validation directly so a regression cannot allocate billion-digit
        # integers inside Fraction while running the test suite.
        for value in ['1e1000000000', '1e-1000000000', '1e38', '1e-19',
                      '123456789012345678901234567890123456789e-18']:
            with self.subTest(value=value), self.assertRaises(ValueError):
                _positive_decimal(value, 'amount')

    def test_ratio_constraints_reject_excess_magnitude_and_precision(self):
        self.edge('company', 'middle', 0)
        for kwargs in [dict(max_ratio=Decimal('1e38')),
                       dict(min_ratio=Decimal('1e-19')),
                       dict(max_ratio=Decimal('1.2345678901234567890'))]:
            with self.subTest(kwargs=kwargs), self.assertRaises(ValueError):
                self.trace(**kwargs)

    def test_trace_validates_stored_amounts_before_use(self):
        for amount in ['1e1000000000', '1e-1000000000', '1e38']:
            for field in ['amount_paid', 'amount_received']:
                with sqlite3.connect(self.db) as conn:
                    conn.execute('DELETE FROM transactions')
                self.edge('company', 'middle', 0)
                with sqlite3.connect(self.db) as conn:
                    conn.execute('UPDATE transactions SET ' + field + '=?', (amount,))
                with self.subTest(amount=amount, field=field), self.assertRaises(ValueError):
                    self.trace()

    def test_eighteen_decimal_places_and_38_digit_coefficients_remain_exact(self):
        self.edge('company', 'middle', 0, '0.000000000000000001')
        self.edge('middle', 'person', 1, '0.000000000000000001')
        self.assertEqual(self.ids(self.trace()), [[1, 2]])
        amount = '99999999999999999999.999999999999999999'
        self.assertEqual(str(_positive_decimal(amount, 'amount')), amount)

    def test_missing_database_is_not_created(self):
        missing = Path(self.temp.name) / 'missing.sqlite'
        with self.assertRaises((sqlite3.OperationalError, FileNotFoundError)):
            trace_paths(missing, '1', 'company')
        self.assertFalse(missing.exists())

    def test_reading_does_not_mutate_database(self):
        self.edge('company', 'middle', 0)
        self.edge('middle', 'person', 1)
        before = self.db.read_bytes()
        self.trace()
        self.assertEqual(before, self.db.read_bytes())


if __name__ == '__main__':
    unittest.main()
