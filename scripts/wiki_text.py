"""Extract a short prose introduction from local Wikitext, without network calls.

This is not a template/Lua renderer. Unknown templates are omitted; common
inline text/link wrappers are handled explicitly instead of leaking parameters.
"""
import html
import re

import mwparserfromhell
from mwparserfromhell.nodes import (Comment, ExternalLink, Heading, HTMLEntity,
                                   Tag, Template, Text, Wikilink)

TEXT_VERSION = 2
MEDIA_NAMESPACES = {'file', 'image', '文件', '檔案', '档案', '图像', '圖像', '圖片', '图片',
                    'category', '分类', '分類'}
OMIT_TAGS = {'ref', 'references', 'gallery', 'table', 'timeline', 'imagemap',
             'math', 'chem', 'score', 'source', 'syntaxhighlight', 'script', 'style'}


def chinese_variants(text):
    """Resolve inline Chinese variant markup before stripping wiki syntax."""
    def choose(match):
        value = match[1]
        if '|' in value:
            flags, value = value.split('|', 1)
            if flags.strip().upper() in ('H', 'A'):
                return ''
        variants = dict(re.findall(r'(zh(?:-[a-z]+)?)\s*:\s*([^;]*)', value))
        if variants:
            return next((variants[k] for k in ('zh-cn', 'zh-hans', 'zh', 'zh-sg', 'zh-tw', 'zh-hant', 'zh-hk') if k in variants), '')
        return value
    return re.sub(r'-\{(.*?)\}-', choose, text, flags=re.S)


def plain_code(code):
    out = []
    for node in code.nodes:
        if isinstance(node, (Text, HTMLEntity)):
            out.append(html.unescape(str(node)))
        elif isinstance(node, Comment):
            continue
        elif isinstance(node, Wikilink):
            target = str(node.title).strip()
            if target.split(':', 1)[0].lower() in MEDIA_NAMESPACES:
                continue
            out.append(plain_code(node.text if node.text is not None else node.title))
        elif isinstance(node, ExternalLink):
            if node.title is not None:
                out.append(plain_code(node.title))
        elif isinstance(node, Template):
            name = str(node.name).strip().lower().replace('_', ' ')
            param = None
            if name == 'lang':
                param = '2'
            elif name.startswith('lang-') or name in {'nowrap', 'nobr', 'small', 'big', 'smaller', 'larger', 'b', 'strong', 'em', 'nihongo', 'ruby', 'ill', 'ilh', 'link-en', 'link-ja', 'le', 'lj', '不换行', '不換行'}:
                param = 'lt' if node.has('lt') else '1'
            if param and node.has(param):
                out.append(plain_code(node.get(param).value))
        elif isinstance(node, Tag):
            tag = str(node.tag).strip().lower()
            if tag in OMIT_TAGS:
                continue
            if tag in {'li', 'dt', 'dd'}:
                out.append('\n*')
            if tag in {'br', 'p', 'div'}:
                out.append('\n\n')
            if node.contents is not None:
                out.append(plain_code(node.contents))
            if tag in {'p', 'div'}:
                out.append('\n\n')
        elif isinstance(node, Heading):
            out.append(plain_code(node.title))
    return ''.join(out)


def extract_summary(text, target_length=600):
    code = mwparserfromhell.parse(chinese_variants(text))
    # Stop at an actual top-level heading, not "==" inside a comment/template.
    lead = []
    for node in code.nodes:
        if isinstance(node, Heading):
            break
        lead.append(node)
    plain = plain_code(mwparserfromhell.wikicode.Wikicode(lead))
    for paragraph in re.split(r'\n\s*\n', plain):
        lines = [line.strip() for line in paragraph.splitlines()
                 if line.strip() and not re.match(r'^\s*[*#;:|!]', line)]
        paragraph = re.sub(r'\s+', ' ', ' '.join(lines)).strip()
        if not paragraph:
            continue
        if len(paragraph) <= target_length:
            return paragraph
        # Prefer whole sentences. A long first sentence is retained in full.
        ends = [m.end() for m in re.finditer(r'[。！？!?](?:[”’」』）)]*)|\.(?=\s|$)', paragraph)]
        if not ends:
            return paragraph
        before_limit = [end for end in ends if end <= target_length]
        return paragraph[:before_limit[-1] if before_limit else ends[0]].strip()
    return ''
