"""Validate IBM AML CSV records and import them atomically into SQLite."""

import csv
import hashlib
import re
import sqlite3
from contextlib import closing
from datetime import datetime
from pathlib import Path

from .numeric import positive_bounded_decimal


IBM_HEADER = [
    "Timestamp", "From Bank", "Account", "To Bank", "Account",
    "Amount Received", "Receiving Currency", "Amount Paid",
    "Payment Currency", "Payment Format", "Is Laundering",
]


def normalize_bank(value: str) -> str:
    """Normalize decimal bank IDs so transaction and account files can join."""
    if not isinstance(value, str) or re.fullmatch(r"[0-9]+", value) is None:
        raise ValueError("Bank ID must contain ASCII decimal digits only")
    return value.lstrip("0") or "0"


def _positive_decimal(value: str, field: str) -> str:
    return str(positive_bounded_decimal(value, field))


def _validate_row(row, source_row):
    if len(row) != len(IBM_HEADER):
        raise ValueError("CSV record {}: expected 11 columns, got {}".format(
            source_row, len(row)))
    try:
        if re.fullmatch(r"[0-9]{4}/[0-9]{2}/[0-9]{2} [0-9]{2}:[0-9]{2}", row[0]) is None:
            raise ValueError("Timestamp must use YYYY/MM/DD HH:MM")
        timestamp = datetime.strptime(row[0], "%Y/%m/%d %H:%M").isoformat()
        from_bank, to_bank = normalize_bank(row[1]), normalize_bank(row[3])
        for index in (2, 4, 6, 8, 9):
            if not row[index].strip():
                raise ValueError("{} cannot be empty".format(IBM_HEADER[index]))
        received = _positive_decimal(row[5], "Amount Received")
        paid = _positive_decimal(row[7], "Amount Paid")
        if row[10] not in ("0", "1"):
            raise ValueError("Is Laundering must be 0 or 1")
        return (timestamp, from_bank, row[2], to_bank, row[4], paid, row[8],
                received, row[6], row[9], int(row[10]), row[1], row[3])
    except ValueError as exc:
        raise ValueError("CSV record {}: {}".format(source_row, exc)) from exc


def _hash_file(path):
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _create_schema(conn):
    conn.execute("""CREATE TABLE IF NOT EXISTS sources (
        sha256 TEXT PRIMARY KEY, file_name TEXT NOT NULL, row_count INTEGER NOT NULL
    )""")
    conn.execute("""CREATE TABLE IF NOT EXISTS transactions (
        id INTEGER PRIMARY KEY,
        source_sha256 TEXT NOT NULL REFERENCES sources(sha256),
        source_row INTEGER NOT NULL,
        timestamp TEXT NOT NULL,
        from_bank TEXT NOT NULL, from_account TEXT NOT NULL,
        to_bank TEXT NOT NULL, to_account TEXT NOT NULL,
        amount_paid TEXT NOT NULL, payment_currency TEXT NOT NULL,
        amount_received TEXT NOT NULL, receiving_currency TEXT NOT NULL,
        payment_format TEXT NOT NULL, is_laundering INTEGER NOT NULL,
        from_bank_raw TEXT NOT NULL, to_bank_raw TEXT NOT NULL,
        UNIQUE(source_sha256, source_row),
        CHECK(is_laundering IN (0, 1))
    )""")
    conn.execute("""CREATE INDEX IF NOT EXISTS transactions_sender_time
        ON transactions(from_bank, from_account, timestamp)""")


def ingest_csv(csv_path, db_path) -> dict:
    """Import a complete file, or roll back every new record on invalid input.

    Identical file contents are imported once. Duplicate-looking CSV records
    within a source remain separate payments. Labels are stored for evaluation.
    Timestamps have no inferred timezone. Source row numbers count CSV records,
    including the header as record 1, rather than physical text lines.
    Amounts must be finite positive decimals with at most 38 coefficient
    digits, exponent >=-18, and magnitude <1e38; excess values are rejected.
    """
    path = Path(csv_path)
    digest = _hash_file(path)
    with closing(sqlite3.connect(db_path)) as conn:
        conn.execute("PRAGMA foreign_keys = ON")
        with conn:
            conn.execute("BEGIN IMMEDIATE")
            _create_schema(conn)
            existing = conn.execute(
                "SELECT row_count FROM sources WHERE sha256 = ?", (digest,)
            ).fetchone()
            if existing is not None:
                return {"source_sha256": digest, "row_count": existing[0],
                        "already_imported": True}
            conn.execute("INSERT INTO sources VALUES (?, ?, 0)", (digest, path.name))
            row_count = 0
            try:
                with path.open("r", encoding="utf-8", newline="") as handle:
                    reader = csv.reader(handle, strict=True)
                    if next(reader, None) != IBM_HEADER:
                        raise ValueError("Expected exact IBM CSV header, including both Account columns")
                    for source_row, row in enumerate(reader, start=2):
                        values = _validate_row(row, source_row)
                        conn.execute("""INSERT INTO transactions (
                            source_sha256, source_row, timestamp, from_bank,
                            from_account, to_bank, to_account, amount_paid,
                            payment_currency, amount_received, receiving_currency,
                            payment_format, is_laundering, from_bank_raw, to_bank_raw
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                                     (digest, source_row) + values)
                        row_count += 1
            except (csv.Error, UnicodeError) as exc:
                raise ValueError("Invalid UTF-8 CSV: {}".format(exc)) from exc
            # Refuse misleading provenance if the input changed during ingestion.
            if _hash_file(path) != digest:
                raise ValueError("Source file changed during ingestion; no records imported")
            conn.execute("UPDATE sources SET row_count = ? WHERE sha256 = ?",
                         (row_count, digest))
        return {"source_sha256": digest, "row_count": row_count,
                "already_imported": False}
