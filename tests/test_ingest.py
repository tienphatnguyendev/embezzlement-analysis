import csv
import hashlib
import sqlite3
import tempfile
import unittest
from pathlib import Path

from embezzlement_analysis.ingest import ingest_csv, normalize_bank


HEADER = ["Timestamp", "From Bank", "Account", "To Bank", "Account",
          "Amount Received", "Receiving Currency", "Amount Paid",
          "Payment Currency", "Payment Format", "Is Laundering"]
ROW = ["2022/09/01 00:20", "001", "000ABC", "010", "000ABC",
       "99.123456789123456789", "Euro", "100.000000000000000001",
       "US Dollar", "Wire", "1"]


class IngestTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.db = self.root / "data.sqlite"

    def write_csv(self, rows, name="source.csv", header=None):
        path = self.root / name
        with path.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.writer(handle)
            writer.writerow(HEADER if header is None else header)
            writer.writerows(rows)
        return path

    def query(self, sql):
        with sqlite3.connect(self.db) as conn:
            return conn.execute(sql).fetchall()

    def test_preserves_both_accounts_exact_amounts_and_source_reference(self):
        path = self.write_csv([ROW])
        result = ingest_csv(path, self.db)
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        self.assertEqual(result, {"source_sha256": digest, "row_count": 1,
                                  "already_imported": False})
        self.assertEqual(self.query("SELECT source_sha256, source_row, timestamp, "
                                    "from_bank,from_account,to_bank,to_account, "
                                    "amount_paid,payment_currency,amount_received, "
                                    "receiving_currency,payment_format,is_laundering "
                                    "FROM transactions"),
                         [(digest, 2, "2022-09-01T00:20:00", "1", "000ABC", "10",
                           "000ABC", "100.000000000000000001", "US Dollar",
                           "99.123456789123456789", "Euro", "Wire", 1)])

    def test_bank_normalization_rejects_non_decimal_identifiers(self):
        self.assertEqual(normalize_bank("00010"), "10")
        self.assertEqual(normalize_bank("000"), "0")
        for value in ["", "1.0", "-1", "+1", "1e2", "ABC", " 1", "１２"]:
            with self.subTest(value=value), self.assertRaises(ValueError):
                normalize_bank(value)

    def test_reimport_by_content_is_skipped_even_if_filename_changes(self):
        path = self.write_csv([ROW])
        first = ingest_csv(path, self.db)
        copy = self.root / "renamed.csv"
        copy.write_bytes(path.read_bytes())
        second = ingest_csv(copy, self.db)
        self.assertTrue(second["already_imported"])
        self.assertEqual(second["source_sha256"], first["source_sha256"])
        self.assertEqual(second["row_count"], 1)
        self.assertEqual(self.query("SELECT count(*) FROM transactions"), [(1,)])
        self.assertEqual(self.query("SELECT count(*) FROM sources"), [(1,)])

    def test_identical_looking_records_remain_separate_payments(self):
        ingest_csv(self.write_csv([ROW, ROW]), self.db)
        self.assertEqual(self.query("SELECT source_row FROM transactions ORDER BY id"),
                         [(2,), (3,)])

    def test_header_must_match_duplicate_account_schema_positionally(self):
        altered = HEADER.copy()
        altered[4] = "Account.1"
        with self.assertRaises(ValueError):
            ingest_csv(self.write_csv([ROW], header=altered), self.db)

    def test_invalid_amounts_roll_back_whole_source_and_keep_existing_data(self):
        ingest_csv(self.write_csv([ROW], name="valid.csv"), self.db)
        for column in [5, 7]:
            for amount in ["-1", "0", "-0.0", "NaN", "sNaN", "Infinity", "-Infinity", "bad"]:
                bad = ROW.copy()
                bad[column] = amount
                path = self.write_csv([ROW, bad], name="bad.csv")
                with self.subTest(column=column, amount=amount), self.assertRaises(ValueError):
                    ingest_csv(path, self.db)
                self.assertEqual(self.query("SELECT count(*) FROM transactions"), [(1,)])
                self.assertEqual(self.query("SELECT count(*) FROM sources"), [(1,)])

    def test_decimal_resource_limits_reject_before_storage_and_roll_back(self):
        ingest_csv(self.write_csv([ROW], name='valid.csv'), self.db)
        for column in [5, 7]:
            for amount in ['1e1000000000', '1e-1000000000', '1e38', '1e-19',
                           '123456789012345678901234567890123456789e-18']:
                bad = ROW.copy()
                bad[column] = amount
                with self.subTest(column=column, amount=amount), self.assertRaises(ValueError):
                    ingest_csv(self.write_csv([ROW, bad], name='too_large.csv'), self.db)
                self.assertEqual(self.query('SELECT count(*) FROM transactions'), [(1,)])
                self.assertEqual(self.query('SELECT count(*) FROM sources'), [(1,)])

    def test_decimal_limit_boundaries_preserve_exact_values(self):
        row = ROW.copy()
        row[5] = '99999999999999999999.999999999999999999'
        row[7] = '0.000000000000000001'
        ingest_csv(self.write_csv([row]), self.db)
        self.assertEqual(self.query('SELECT amount_paid,amount_received FROM transactions'),
                         [('1E-18', '99999999999999999999.999999999999999999')])

    def test_invalid_timestamp_label_and_missing_values_are_rejected(self):
        for column, value in [(0, "2022/02/30 00:00"), (0, "2022-09-01T00:20:00"),
                              (10, "2"), (10, "true"), (1, "bank"), (2, ""),
                              (4, ""), (6, ""), (8, ""), (9, "")]:
            bad = ROW.copy()
            bad[column] = value
            with self.subTest(column=column, value=value), self.assertRaises(ValueError):
                ingest_csv(self.write_csv([ROW, bad]), self.db)

    def test_wrong_column_count_is_rejected(self):
        for row in [ROW[:-1], ROW + ["extra"], []]:
            with self.subTest(row=row), self.assertRaises(ValueError):
                ingest_csv(self.write_csv([row]), self.db)

    def test_record_number_counts_csv_records_not_physical_lines(self):
        multiline = ROW.copy()
        multiline[9] = "Wire\nmanual"
        ingest_csv(self.write_csv([multiline, ROW]), self.db)
        self.assertEqual(self.query("SELECT source_row FROM transactions ORDER BY id"),
                         [(2,), (3,)])

    def test_empty_file_has_no_valid_header(self):
        path = self.root / "empty.csv"
        path.write_bytes(b"")
        with self.assertRaises(ValueError):
            ingest_csv(path, self.db)

    def test_bad_csv_syntax_or_encoding_does_not_leave_partial_rows(self):
        original = self.write_csv([ROW], name="valid.csv")
        ingest_csv(original, self.db)
        for suffix in [b'"unterminated', b'\xff,broken\n']:
            path = self.root / "broken.csv"
            path.write_bytes(original.read_bytes() + suffix)
            with self.subTest(suffix=suffix), self.assertRaises(ValueError):
                ingest_csv(path, self.db)
            self.assertEqual(self.query("SELECT count(*) FROM transactions"), [(1,)])
            self.assertEqual(self.query("SELECT count(*) FROM sources"), [(1,)])


if __name__ == "__main__":
    unittest.main()
