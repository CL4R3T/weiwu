#!/usr/bin/env python3
"""Offline-only regression checks. Does not need PostgreSQL or a full dump."""
import bz2
import gzip
import hashlib
import importlib.util
from pathlib import Path
import sys
import tempfile
import types
import unittest

# Loading only the local validator does not need the actual parsing/DB drivers.
for module in ('mwparserfromhell', 'psycopg', 'psycopg.sql'):
    if module not in sys.modules:
        sys.modules[module] = types.ModuleType(module)
spec = importlib.util.spec_from_file_location('wiki_snapshot', Path(__file__).with_name('wiki_snapshot.py'))
wiki = importlib.util.module_from_spec(spec)
spec.loader.exec_module(wiki)


def make_dump(directory):
    # Compressed mock archives large enough for the minimum-size check.
    xml = bz2.compress(b'<mediawiki>' + bytes(range(256)) * 8 + b'</mediawiki>')
    cats = gzip.compress(b"CREATE TABLE `categorylinks` (\n  `cl_from` int,\n  `cl_to` varbinary(255)\n) ENGINE=InnoDB;\n"
                         b"INSERT INTO `categorylinks` VALUES (1,'Example');\n")
    files = {wiki.FILES[0]: xml, wiki.FILES[1]: cats}
    for name, data in files.items():
        (directory / name).write_bytes(data)
    # /latest/ uses "latest" filenames, whereas Wikimedia MD5 manifests use
    # the real release date. Test the exact real-world naming distinction.
    checksums = ''.join(hashlib.md5(data).hexdigest() + '  ' + name.replace('zhwiki-latest-', 'zhwiki-20261101-') + '\n'
                        for name, data in files.items())
    (directory / wiki.CHECKSUM_FILE).write_text(checksums, encoding='utf-8')


class LocalSnapshots(unittest.TestCase):
    def test_dump_insert_layouts(self):
        ddl = "CREATE TABLE `linktarget` (\n  `lt_id` int,\n  `lt_title` text\n) ENGINE=InnoDB;\n"
        inserts = (" INSERT INTO linktarget VALUES\n(1, 'One'),\n(2,'Two');\n"
                   "INSERT INTO `linktarget` (`lt_title`, `lt_id`) VALUES(_binary 'Three',3);\n")
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / 'targets.gz'
            path.write_bytes(gzip.compress((ddl + inserts).encode()))
            rows = wiki.dump_rows(path, 'linktarget', ['lt_id', 'lt_title'])
            self.assertEqual([(i, wiki.dump_title(t)) for i, t in rows],
                             [('1','One'),('2','Two'),('3','Three')])
            path.write_bytes(gzip.compress((ddl + 'INSERT DELAYED INTO linktarget VALUES (1,2);').encode()))
            with self.assertRaisesRegex(ValueError, 'unsupported INSERT header'):
                list(wiki.dump_rows(path, 'linktarget', ['lt_id']))

    def test_modern_graph(self):
        def write_table(path, name, columns, rows):
            ddl = ',\n'.join(f'  `{col}` TEXT' for col in columns)
            path.write_bytes(gzip.compress(
                f'CREATE TABLE `{name}` (\n{ddl}\n) ENGINE=InnoDB;\nINSERT INTO `{name}` VALUES {rows};\n'.encode()))
        with tempfile.TemporaryDirectory() as temp:
            folder = Path(temp)
            cats, targets = folder / 'cats.gz', folder / 'targets.gz'
            write_table(targets, 'linktarget', ['lt_id','lt_namespace','lt_title'],
                        "(90,14,'植物'),(91,14,'蕨类'),(92,0,'Ignore')")
            write_table(cats, 'categorylinks', ['cl_from','cl_sortkey','cl_timestamp','cl_sortkey_prefix','cl_type','cl_collation_id','cl_target_id'],
                        "(1,0xFF,'2026-01-01','a),(b','page',2,91),(42,'','','','subcat',2,90)")
            catalog = wiki.category_catalog(cats, folder / 'cache', targets)
            try:
                catalog.execute("INSERT INTO category_pages VALUES (42,'蕨类')")
                roots = wiki.create_topic_map(catalog, 7)
                raw = [r[0] for r in catalog.execute('SELECT category FROM links WHERE page_id=1')]
                self.assertEqual(raw, ['蕨类'])
                self.assertEqual([t['name'] for t in wiki.match_categories(catalog, roots, raw)], ['植物'])
            finally:
                catalog.close()

    def test_correct_files_are_accepted(self):
        with tempfile.TemporaryDirectory() as temp:
            folder = Path(temp) / '2026-11'
            folder.mkdir()
            make_dump(folder)
            self.assertEqual(wiki.verify_local(folder), tuple(folder / f for f in wiki.FILES))

    def test_missing_file_rejected_before_db_mutation(self):
        with tempfile.TemporaryDirectory() as temp:
            folder = Path(temp) / '2026-11'
            folder.mkdir()
            make_dump(folder)
            (folder / wiki.FILES[1]).unlink()
            with self.assertRaisesRegex(RuntimeError, 'Missing local dump files'):
                wiki.stage(folder, '2026-11')

    def test_corrupted_archive_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            folder = Path(temp) / '2026-11'
            folder.mkdir()
            make_dump(folder)
            with (folder / wiki.FILES[0]).open('ab') as stream:
                stream.write(b'corrupt')
            with self.assertRaisesRegex(RuntimeError, 'Checksum mismatch'):
                wiki.verify_local(folder)

    def test_wrong_snapshot_month_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            folder = Path(temp) / '2026-12'
            folder.mkdir()
            make_dump(folder)
            with self.assertRaisesRegex(RuntimeError, 'matching snapshot'):
                wiki.verify_local(folder)

    def test_empty_month_parent_is_noop(self):
        with tempfile.TemporaryDirectory() as temp:
            wiki.automatic(Path(temp), max_depth=7, should_activate=True)

    def test_downloader_removed(self):
        self.assertFalse(hasattr(wiki, 'download'))
        self.assertFalse(hasattr(wiki, 'download_file'))
        self.assertFalse(hasattr(wiki, 'BASE'))


if __name__ == '__main__':
    unittest.main()
