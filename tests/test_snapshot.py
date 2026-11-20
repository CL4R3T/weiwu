import bz2
import gzip
from pathlib import Path
import tempfile
import unittest

from scripts.wiki_snapshot import (category_catalog, create_topic_map, eligible,
                                   parse_sections, topic_roots, wiki_pages)
from scripts.d1_to_postgres import copy_value


class SnapshotTests(unittest.TestCase):
    def test_sections_and_summary(self):
        sections, summary = parse_sections("'''猫'''是动物。\n==历史==\n内容\n===早期===\n内容\n==参考资料==\n引文")
        self.assertEqual([x['level'] for x in sections], [1, 2, 1])
        self.assertIn('猫是动物', summary)
        self.assertTrue(eligible('猫', 801, sections, ['动物'], {'minChars': 800}))
        self.assertFalse(eligible('猫', 100, sections, ['动物'], {'minChars': 800}))

    def test_xml_and_category_graph(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            xml = """<mediawiki xmlns='http://www.mediawiki.org/xml/export-0.11/'>
            <page><title>示例猫</title><ns>0</ns><id>10</id><revision><id>100</id><text>'''猫'''。\n==历史==\n内容\n===最初===\n内容</text></revision></page>
            <page><title>Category:火车</title><ns>14</ns><id>88</id><revision><id>101</id><text>分类</text></revision></page>
            <page><title>小猫</title><ns>0</ns><id>11</id><redirect title='示例猫'/><revision><id>102</id><text>#REDIRECT [[示例猫]]</text></revision></page>
            </mediawiki>"""
            (root/'test.xml.bz2').write_bytes(bz2.compress(xml.encode()))
            rows = list(wiki_pages(root/'test.xml.bz2'))
            self.assertEqual(len(rows), 3)
            self.assertEqual(rows[0][2], 10)
            self.assertEqual(rows[2][3], '示例猫')
            sample = "CREATE TABLE `categorylinks` (\n  `cl_from` int,\n  `cl_to` text,\n  `cl_sortkey` text,\n  `cl_type` int\n) ENGINE=InnoDB;\nINSERT INTO `categorylinks` VALUES (10,'火车','',0),(88,'交通','',0);\n"
            (root/'categories.sql.gz').write_bytes(gzip.compress(sample.encode()))
            catalog = category_catalog(root/'categories.sql.gz', root/'cache.sqlite3')
            catalog.execute("INSERT INTO category_pages VALUES(88,'火车')")
            catalog.commit()
            create_topic_map(catalog, 2)
            self.assertGreater(catalog.execute("SELECT COUNT(*) FROM topic_map WHERE category='火车'").fetchone()[0], 0)
            catalog.close()

    def test_helpers(self):
        self.assertEqual(len(topic_roots()) > 80, True)
        self.assertEqual(copy_value(None), r'\N')
        self.assertEqual(copy_value('a\tb\n\\c'), r'a\tb\n\\c')


if __name__ == '__main__':
    unittest.main()
