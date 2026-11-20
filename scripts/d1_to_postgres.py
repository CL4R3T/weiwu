#!/usr/bin/env python3
"""Convert a FULL SQLite/D1 export to lossless PostgreSQL COPY data.

Usage: python3 scripts/d1_to_postgres.py --sqlite old.sqlite3 --output postgres/02_data.sql
This tool does not extract a remote D1 database; it requires a complete dump.
"""
import argparse
import os
import sqlite3
from pathlib import Path

TABLES = [
    'users', 'sessions', 'captchas', 'rate_limits', 'articles', 'exclusions',
    'pool', 'source_jobs', 'daily', 'games', 'guesses', 'votes', 'aliases',
    'alias_proposals', 'comments', 'settings', 'audit', 'selection_skips',
    'category_nodes', 'article_topics', 'topic_queue', 'topic_members',
]


def copy_value(value):
    if value is None:
        return r'\N'
    if isinstance(value, bytes):
        return '\\x' + value.hex()
    return str(value).replace('\\', '\\\\').replace('\t', r'\t').replace('\r', r'\r').replace('\n', r'\n')


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--sqlite', type=Path, required=True)
    ap.add_argument('--output', type=Path, required=True)
    args = ap.parse_args()
    if not args.sqlite.is_file():
        ap.error('SQLite database missing; first obtain a FULL D1 export')
    if args.output.exists():
        ap.error('Output already exists; refusing to overwrite an existing backup')
    conn = sqlite3.connect(f'file:{args.sqlite}?mode=ro', uri=True)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(args.output, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    totals = {}
    try:
        with os.fdopen(fd, 'w', encoding='utf-8', newline='\n') as out:
            out.write('-- Lossless data export; PRIVATE: contains accounts and password hashes.\n')
            out.write('BEGIN;\n')
            for name in TABLES:
                info = conn.execute(f'PRAGMA table_info("{name}")').fetchall()
                if not info:
                    raise RuntimeError(f'Table {name} missing: input is not a full site database')
                cols = [row[1] for row in info]
                identifiers = ','.join('"' + c.replace('"', '""') + '"' for c in cols)
                out.write(f'COPY "{name}" ({identifiers}) FROM stdin;\n')
                count = 0
                for row in conn.execute(f'SELECT {identifiers} FROM "{name}"'):
                    out.write('\t'.join(map(copy_value, row)) + '\n')
                    count += 1
                out.write('\\.\n')
                totals[name] = count
            out.write('COMMIT;\n')
    except BaseException:
        args.output.unlink(missing_ok=True)
        raise
    finally:
        conn.close()
    for table, count in totals.items():
        print(f'{table}: {count}')
    print(f'Wrote {args.output} ({args.output.stat().st_size:,} bytes)')


if __name__ == '__main__':
    main()
