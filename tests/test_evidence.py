import csv
import hashlib
import tempfile
import unittest
from pathlib import Path

from embezzlement_analysis.evidence import load_table


class EvidenceTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name) / 'input.csv'

    def test_preserves_identity_and_fingerprints_original_bytes(self):
        raw = b'id,value\r\n000A, A \r\n000B,B\r\n'
        self.path.write_bytes(raw)
        rows, source = load_table(self.path, ['id', 'value'])
        self.assertEqual(rows[0], {'id': '000A', 'value': ' A ', '_source_row': 2})
        self.assertEqual(source['sha256'], hashlib.sha256(raw).hexdigest())
        self.assertEqual(source['row_count'], 2)

    def test_multiline_field_uses_csv_record_reference(self):
        self.path.write_text('id,value\nA,"line1\nline2"\nB,value\n')
        rows, _ = load_table(self.path, ['id', 'value'])
        self.assertEqual(rows[1]['_source_row'], 3)

    def test_rejects_wrong_headers_encoding_and_malformed_records(self):
        for raw in [b'value,id\nx,A\n', b'id,value\nA\n', b'id,value\nA,\xff\n', b'id,value\nA,"unclosed']:
            self.path.write_bytes(raw)
            with self.assertRaises(ValueError):
                load_table(self.path, ['id', 'value'])

    def test_empty_table_is_valid_supplied_evidence(self):
        self.path.write_text('id,value\n')
        rows, source = load_table(self.path, ['id', 'value'])
        self.assertEqual(rows, [])
        self.assertEqual(source['row_count'], 0)
