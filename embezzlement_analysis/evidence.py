"""Read small evidence tables from one immutable byte snapshot."""

import csv
import hashlib
import io
from pathlib import Path


MAX_TABLE_BYTES = 64 * 1024 * 1024


def load_table(path, fields):
    """Return exact strings, CSV record numbers, and their source fingerprint.

    Preserve identity whitespace. Consumers decide which descriptive fields
    may be normalized. Never hash a separate read of the source file.
    """
    path = Path(path)
    with path.open('rb') as stream:
        raw = stream.read(MAX_TABLE_BYTES + 1)
    if len(raw) > MAX_TABLE_BYTES:
        raise ValueError('%s exceeds the 64 MiB evidence-table limit' % path.name)
    rows = []
    try:
        reader = csv.reader(io.StringIO(raw.decode('utf-8-sig'), newline=''), strict=True)
        if next(reader, None) != list(fields):
            raise ValueError('%s header must be: %s' % (path.name, ','.join(fields)))
        for row_number, values in enumerate(reader, 2):
            if len(values) != len(fields):
                raise ValueError('%s CSV record %s has the wrong field count' % (path.name, row_number))
            rows.append(dict(zip(fields, values), _source_row=row_number))
    except (csv.Error, UnicodeError) as error:
        raise ValueError('%s is not valid UTF-8 CSV: %s' % (path.name, error)) from error
    return rows, {'file_name': path.name, 'sha256': hashlib.sha256(raw).hexdigest(),
                  'row_count': len(rows)}
