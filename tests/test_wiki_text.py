import unittest

from scripts.wiki_text import extract_summary


class SummaryTests(unittest.TestCase):
    def test_image_options_and_caption_are_removed(self):
        text = "[[File:Temple.jpg|thumb|right|280px|伊拉斯謨斯的[[演化]]诗插图。]]\n'''生物学史'''是人类研究生命的历史。\n\n第二段。\n==历史==\n正文"
        self.assertEqual(extract_summary(text), '生物学史是人类研究生命的历史。')

    def test_localized_media_and_nested_captions(self):
        for namespace in ('File', 'Image', '文件', '檔案', '图像', '圖像'):
            self.assertEqual(extract_summary(f'[[{namespace}:图.jpg|缩略图|{{{{lang|en|Caption}}}}及[[链接|文字]]]]\n正文。'), '正文。')

    def test_noise_and_reference_content(self):
        text = '{{Infobox|name=不应出现}}\n<gallery>File:A.jpg|图注</gallery>\n{| class="wikitable"\n|表格\n|}\n正文<ref>{{cite web|title=参考标题}}</ref>内容。[[Category:历史]]'
        self.assertEqual(extract_summary(text), '正文内容。')

    def test_inline_templates_and_links(self):
        self.assertEqual(extract_summary("'''猫'''（{{lang|en|cat}}）是{{nowrap|一种}}[[动物|哺乳动物]]。"), '猫（cat）是一种哺乳动物。')
        self.assertEqual(extract_summary('{{ill|达尔文|en|Charles Darwin}}是人名。'), '达尔文是人名。')

    def test_variants(self):
        self.assertEqual(extract_summary('-{zh-hans:历史;zh-hant:歷史;}-是一门学科。'), '历史是一门学科。')

    def test_sentence_boundary(self):
        first = '甲' * 350 + '。'
        self.assertEqual(extract_summary(first + '乙' * 350 + '。'), first)
        long_sentence = '甲' * 650 + '。'
        self.assertEqual(extract_summary(long_sentence + '第二句。'), long_sentence)

    def test_first_prose_paragraph(self):
        self.assertEqual(extract_summary('* 列表项\n\n首段第一行，\n第二行。\n\n次段。'), '首段第一行， 第二行。')

    def test_comment_heading_is_not_a_section(self):
        self.assertEqual(extract_summary('<!--\n==伪标题==\n-->介绍。\n==真标题==\n正文'), '介绍。')

    def test_html_entities_and_no_prose(self):
        self.assertEqual(extract_summary('A &amp; B 是名称。'), 'A & B 是名称。')
        self.assertEqual(extract_summary('{{Infobox|name=甲}}\n[[File:A.jpg|thumb|图注]]\n==历史==\n正文'), '')


if __name__ == '__main__':
    unittest.main()
