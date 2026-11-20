#!/usr/bin/env python3
"""Verify manually downloaded Chinese Wikipedia dumps, stage and activate TOC snapshots.

Requires psycopg[binary] and mwparserfromhell. On the server:
  # Put matching official dumps and their MD5 manifest in wiki-dumps/2026-11.
  python scripts/wiki_snapshot.py check --directory wiki-dumps/2026-11
  python scripts/wiki_snapshot.py stage --directory wiki-dumps/2026-11 --snapshot 2026-11
  python scripts/wiki_snapshot.py classify --directory wiki-dumps/2026-11 --snapshot 2026-11
  python scripts/wiki_snapshot.py activate --snapshot 2026-11

  # For recurring runs after manually dropping files into month folders:
  python scripts/wiki_snapshot.py auto --directory wiki-dumps --activate

Never touches player tables; activation retains historical article IDs.
"""
from contextlib import contextmanager

import argparse
import ast
import bz2
import datetime as dt
import gzip
import hashlib
import html
import json
import os
from pathlib import Path
import re
import sqlite3
import sys
import tempfile
import time
import unicodedata
import xml.etree.ElementTree as ET

import mwparserfromhell
import psycopg
from psycopg import sql
from tqdm import tqdm

if __package__:
    from .wiki_text import extract_summary, TEXT_VERSION
else:
    from wiki_text import extract_summary, TEXT_VERSION

FILES = [
    'zhwiki-latest-pages-articles-multistream.xml.bz2',
    'zhwiki-latest-categorylinks.sql.gz',
]
CHECKSUM_FILE = 'zhwiki-latest-md5sums.txt'
NAMESPACE = '{http://www.mediawiki.org/xml/export-0.11/}'
HEAD = re.compile(r'^(={2,6})\s*(.*?)\s*\1\s*$', re.M)
SQL_VALUE = r"(?:(?:_binary\s*)?'(?:\\.|[^'\\])*'|0x[0-9a-fA-F]*|-?\d+|NULL)"
SQL_ROW = re.compile(rf"\(\s*({SQL_VALUE}(?:\s*,\s*{SQL_VALUE})*)\s*\)\s*([,;])")


def dump_columns(path, table):
    with gzip.open(path, 'rt', encoding='utf-8', errors='replace') as stream:
        for line in stream:
            if line.startswith(f'CREATE TABLE `{table}`'):
                columns = []
                for line in stream:
                    if line.startswith(')'):
                        return columns
                    match = re.match(r'\s*`([a-z_]+)`', line)
                    if match:
                        columns.append(match[1])
            if line.startswith('INSERT INTO'):
                break
    raise ValueError(f'Missing CREATE TABLE for {table}')


def dump_rows(path, table, fields):
    columns = dump_columns(path, table)
    table_name = re.escape(table)
    header = re.compile(
        rf'\s*INSERT\s+(?:IGNORE\s+)?INTO\s+(?:`{table_name}`|{table_name})\s*'
        r'(?:\((?P<columns>[\w`,\s]+)\)\s*)?VALUES\b', re.I)
    value = re.compile(SQL_VALUE)
    in_values = False
    saw_insert = False
    with measured_file(path, table) as raw, gzip.open(raw, 'rt', encoding='utf-8', errors='replace') as stream:
        for line_no, line in enumerate(stream, 1):
            pos = 0
            if not in_values:
                if line.lstrip()[:6].upper() != 'INSERT':
                    continue
                start = header.match(line)
                if not start:
                    raise ValueError(f'{table}:{line_no}: unsupported INSERT header: {line[:160]!r}')
                explicit = start['columns']
                order = [c.strip().strip("`") for c in explicit.split(',')] if explicit else columns
                indices = [order.index(field) for field in fields]
                pos = start.end()
                in_values = saw_insert = True
            while pos < len(line):
                if line[pos].isspace():
                    pos += 1
                    continue
                match = SQL_ROW.match(line, pos)
                if not match:
                    raise ValueError(f'{table}:{line_no}: unsupported VALUES syntax at offset {pos}: {line[pos:pos+160]!r}')
                cells = value.findall(match[1])
                if len(cells) != len(order):
                    raise ValueError(f'Unexpected column count in {table}')
                yield tuple(cells[i] for i in indices)
                if match[2] == ';':
                    in_values = False
                    break
                pos = match.end()
    if not saw_insert or in_values:
        raise ValueError(f'{table}: missing or incomplete INSERT statements in {path.name}')


def dump_title(cell):
    cell = cell.removeprefix('_binary').lstrip()
    if cell.startswith("'"):
        return mysql_unescape(cell[1:-1])
    if cell.startswith('0x'):
        return bytes.fromhex(cell[2:]).decode().replace('_', ' ')
    raise ValueError('Unexpected category title format')


def db():
    url = os.environ.get('DATABASE_URL')
    if not url:
        raise RuntimeError('DATABASE_URL is required')
    return psycopg.connect(url)


progress_options = dict(disable=None, dynamic_ncols=True, mininterval=0.5)


@contextmanager
def measured_file(path, label):
    with path.open('rb') as raw, tqdm.wrapattr(
        raw, 'read', total=path.stat().st_size, desc=label, **progress_options
    ) as measured:
        yield measured


def verify_local(directory):
    """Read only local files. Never downloads or modifies the supplied archives."""
    if not directory.is_dir():
        raise RuntimeError(f'Snapshot folder not found: {directory}')
    needed = [*FILES, CHECKSUM_FILE]
    missing = [name for name in needed if not (directory / name).is_file()]
    if missing:
        raise RuntimeError('Missing local dump files in {}: {}. Download all three from the same Wikimedia snapshot.'.format(
            directory, ', '.join(missing)))
    checksums = {}
    with (directory / CHECKSUM_FILE).open('rt', encoding='utf-8') as source:
        for line in source:
            parts = line.strip().split()
            if len(parts) == 2 and re.fullmatch(r'[0-9a-fA-F]{32}', parts[0]):
                checksums[parts[1].lstrip('*').removeprefix('./')] = parts[0].lower()
    # The /latest/ symlinks are named "zhwiki-latest-...", but Wikimedia's
    # md5sums.txt contains the real run date: "zhwiki-YYYYMMDD-...".
    # Resolve both inputs to one and the same release before verifying bytes.
    dated = {}
    for name, digest in checksums.items():
        found = re.fullmatch(r'zhwiki-(\d{8})-(.+)', name)
        if found:
            dated[(found[1], found[2])] = digest
    month = directory.name.replace('-', '') if re.fullmatch(r'20\d{2}-(0[1-9]|1[0-2])', directory.name) else None
    common_runs = sorted({
        date for date, suffix in dated if (not month or date.startswith(month))
    })
    common_runs = [date for date in common_runs if all(
        (date, name.removeprefix('zhwiki-latest-')) in dated for name in FILES)]
    if common_runs:
        release = common_runs[-1]
        expected = {name: dated[(release, name.removeprefix('zhwiki-latest-'))] for name in FILES}
        print('Official checksum release:', release)
    elif all(name in checksums for name in FILES):
        expected = {name: checksums[name] for name in FILES}
    else:
        raise RuntimeError(
            'MD5 list lacks a complete matching snapshot for {}. '
            'Download all three files together from the same Wikimedia release.'.format(directory))
    paths = [directory / name for name in FILES]
    if 'cl_target_id' in dump_columns(paths[1], 'categorylinks'):
        suffix = 'linktarget.sql.gz'
        dated_name = f'zhwiki-{common_runs[-1]}-{suffix}' if common_runs else ''
        latest_name = 'zhwiki-latest-' + suffix
        name = dated_name if dated_name and (directory / dated_name).is_file() else latest_name
        digest = checksums.get(dated_name or latest_name)
        if not digest or not (directory / name).is_file():
            raise RuntimeError(f'Missing matching {dated_name or latest_name} or its checksum')
        expected[name] = digest
        paths.append(directory / name)
    for path in paths:
        name = path.name
        if path.stat().st_size < 100:
            raise RuntimeError(f'Dump file is unexpectedly small: {path}')
        md5 = hashlib.md5()
        with measured_file(path, f'Checking {name}') as stream:
            for chunk in iter(lambda: stream.read(8 * 1024 * 1024), b''):
                md5.update(chunk)
        if md5.hexdigest() != expected[name]:
            raise RuntimeError(f'Checksum mismatch for {path}; do not use this dump; check its month and re-download it')
        print('Verified local:', path.name, f'({path.stat().st_size:,} bytes)')
    return tuple(paths)


def mysql_unescape(s):
    return re.sub(r'\\(.)', lambda m: {'n': '\n', 'r': '\r', 't': '\t', '0': '\0'}.get(m[1], m[1]), s).replace('_', ' ')


def category_catalog(path, cache, target_path=None):
    conn = sqlite3.connect(cache)
    conn.execute('PRAGMA journal_mode=WAL')
    conn.execute('PRAGMA synchronous=NORMAL')
    conn.execute('CREATE TABLE IF NOT EXISTS links(page_id INTEGER,category TEXT)')
    conn.execute('CREATE TABLE IF NOT EXISTS category_pages(page_id INTEGER PRIMARY KEY,name TEXT UNIQUE)')
    conn.execute('DELETE FROM links')
    conn.execute('DELETE FROM category_pages')
    if target_path:
        conn.execute('CREATE TEMP TABLE targets(id INTEGER PRIMARY KEY,title TEXT NOT NULL)')
        targets = dump_rows(target_path, 'linktarget', ['lt_id', 'lt_namespace', 'lt_title'])
        conn.executemany('INSERT INTO targets VALUES (?,?)',
                         ((int(i), dump_title(title)) for i, ns, title in targets if ns == '14'))
        edges = dump_rows(path, 'categorylinks', ['cl_from', 'cl_target_id'])
        conn.executemany('INSERT INTO links VALUES (?,(SELECT title FROM targets WHERE id=?))', edges)
        if conn.execute('SELECT 1 FROM links WHERE category IS NULL LIMIT 1').fetchone():
            raise ValueError('Unresolved category target ID; check dump releases')
    else:
        edges = dump_rows(path, 'categorylinks', ['cl_from', 'cl_to'])
        conn.executemany('INSERT INTO links VALUES (?,?)', ((int(i), dump_title(title)) for i, title in edges))
    count = conn.execute('SELECT COUNT(*) FROM links').fetchone()[0]
    if not count:
        raise ValueError('No category links imported')
    conn.commit()
    conn.execute('CREATE INDEX IF NOT EXISTS links_page ON links(page_id)')
    conn.execute('CREATE INDEX IF NOT EXISTS links_category ON links(category)')
    conn.commit()
    print('Category links imported:', count)
    return conn


def normalize(s):
    s = unicodedata.normalize('NFKC', s).lower()
    return ''.join(c for c in s if not c.isspace() and unicodedata.category(c)[0] not in ('P', 'S'))


def strip_wiki(s):
    try:
        return html.unescape(mwparserfromhell.parse(s).strip_code(normalize=True, collapse=True)).strip()
    except Exception:
        return re.sub(r'<[^>]+>|\{\{[^{}]*\}\}', '', s).strip()


def parse_sections(text):
    sections, counters = [], [0] * 6
    matches = list(HEAD.finditer(text))
    for match in matches:
        raw_level = len(match[1]); level = raw_level - 1
        heading = strip_wiki(match[2]).strip('= \t')
        if not heading:
            continue
        counters[level - 1] += 1
        for i in range(level, len(counters)):
            counters[i] = 0
        number = '.'.join(str(n) for n in counters[:level] if n)
        sections.append({'text': heading, 'number': number, 'level': level})
    summary = extract_summary(text)
    return sections, summary


def eligible(title, chars, sections, categories, settings):
    if chars < int(settings.get('minChars', 800)):
        return False
    blocked = settings.get('sensitiveTerms', [])
    if any(term and term in title + ' '.join(categories) for term in blocked):
        return False
    if re.search(r'第[\d０-９一二三四五六七八九十百千万零〇两兩]+[届屆]', title):
        return False
    parent = ''
    for entry in sections:
        if entry['level'] == 1:
            parent = entry['text']
        if entry['level'] == 2 and not re.match(r'^(参见|參見|参考|參考|注释|註釋|注釋|外部链接|外部連結|相关条目|相關條目|引用|脚注|腳註|来源|來源|资料来源|資料來源)', parent):
            return True
    return False


def default_rules():
    source = (Path(__file__).resolve().parent.parent / 'lib/server/core.ts').read_text(encoding='utf-8')
    match = re.search(r'sensitiveTerms:(\[[^\]]*\])', source)
    terms = ast.literal_eval(match[1]) if match else []
    return {'minChars': 800, 'minViews': 3, 'sensitiveTerms': terms}


def wiki_pages(path):
    with measured_file(path, 'Reading article dump') as measured, bz2.open(measured, 'rb') as source:
        context = ET.iterparse(source, events=('start', 'end'))
        _, root = next(context)
        namespace = root.tag.split('}')[0] + '}' if '}' in root.tag else ''
        for event, element in context:
            if event != 'end' or element.tag.rsplit('}', 1)[-1] != 'page':
                continue
            def item(name):
                node = element.find(namespace + name)
                return node.text if node is not None and node.text is not None else ''
            ns = int(item('ns') or -1)
            title = item('title')
            pageid = int(item('id') or 0)
            redirect = element.find(namespace + 'redirect')
            revision = element.find(namespace + 'revision')
            content = revision.find(namespace + 'text') if revision is not None else None
            revid = revision.find(namespace + 'id') if revision is not None else None
            text = content.text if content is not None and content.text else ''
            yield ns, title, pageid, redirect.attrib.get('title') if redirect is not None else '', revid.text if revid is not None else '', text
            root.clear()


def stage(directory, snapshot, max_pages=None):
    # Before truncating any staging tables, verify every local input.
    compressed, category_file, *targets = verify_local(directory)
    cache = directory / 'category-cache.sqlite3'
    catalog = category_catalog(category_file, cache, *targets)
    with db() as pgconn:
        with pgconn.cursor() as cur:
            cur.execute('CREATE TABLE IF NOT EXISTS wiki_stage_articles (LIKE articles INCLUDING ALL)')
            cur.execute('CREATE TABLE IF NOT EXISTS wiki_stage_redirects(source text PRIMARY KEY,target text NOT NULL,normalized text NOT NULL)')
            cur.execute('CREATE TABLE IF NOT EXISTS wiki_stage_topics (LIKE article_topics INCLUDING ALL)')
            cur.execute('TRUNCATE wiki_stage_articles, wiki_stage_redirects, wiki_stage_topics')
            # A single set of staging tables is shared by all snapshot IDs.
            cur.execute("UPDATE wiki_snapshots SET state='superseded' WHERE state IN ('staging','classified') AND id<>%s", (snapshot,))
            cur.execute('INSERT INTO wiki_snapshots(id,source_date,state) VALUES(%s,%s,%s) ON CONFLICT(id) DO UPDATE SET state=EXCLUDED.state', (snapshot, snapshot, 'staging'))
            cur.execute("SELECT value FROM settings WHERE key='rules'")
            row = cur.fetchone()
            rules = {**default_rules(), **(json.loads(row[0]) if row else {})}
        pgconn.commit()
        article_count = 0
        category_pages = []
        redirects = []
        with pgconn.cursor() as cur:
            with cur.copy('COPY wiki_stage_articles (id,title,canonical,data,category,chars,views,fetched,filter_version,status,featured) FROM STDIN') as copy:
                for ns, title, pageid, redirect, revid, text in wiki_pages(compressed):
                    if ns == 14:
                        category_pages.append((pageid, title.split(':', 1)[-1].replace('_', ' ')))
                        if len(category_pages) >= 10_000:
                            catalog.executemany('INSERT OR IGNORE INTO category_pages VALUES (?,?)', category_pages)
                            category_pages.clear()
                        continue
                    if ns != 0 or not pageid:
                        continue
                    if redirect:
                        redirects.append((title, redirect))
                        continue
                    if len(re.sub(r'\s+', '', text)) < int(rules.get('minChars', 800)):
                        continue
                    cats = [row[0] for row in catalog.execute('SELECT category FROM links WHERE page_id=?', (pageid,))]
                    sections, summary = parse_sections(text)
                    # The user's minimum is visible extracted characters, not Wikitext markup.
                    plain_chars = len(re.sub(r'\s+', '', strip_wiki(text)))
                    if not eligible(title, plain_chars, sections, cats, rules):
                        continue
                    payload = {'id': str(pageid), 'title': title, 'canonical': title,
                               'aliases': [title], 'sections': sections, 'summary': summary, 'textVersion': TEXT_VERSION,
                               'categories': cats, 'category': '待归类', 'topics': [],
                               'revision': int(revid or 0), 'chars': plain_chars,
                               'views': None, 'taxonomyVersion': 1, 'snapshot': snapshot}
                    copy.write_row((pageid, title, title, json.dumps(payload, ensure_ascii=False),
                                    '待归类', payload['chars'], None, int(time.time() * 1000),
                                    1, 'pending_views', 0))
                    article_count += 1
                    if article_count % 100_000 == 0:
                        print('Staged eligible articles:', article_count, file=sys.stderr)
                    if max_pages and article_count >= max_pages:
                        break
        if category_pages:
            catalog.executemany('INSERT OR IGNORE INTO category_pages VALUES (?,?)', category_pages)
        catalog.commit()
        with pgconn.cursor() as cur:
            with cur.copy('COPY wiki_stage_redirects(source,target,normalized) FROM STDIN') as copy:
                for row in tqdm(redirects, desc='Staging redirects', unit='redirect', **progress_options):
                    copy.write_row((*row, normalize(row[0])))
            cur.execute('UPDATE wiki_snapshots SET article_count=%s WHERE id=%s', (article_count, snapshot))
        pgconn.commit()
        print('Staged:', article_count, 'articles;', len(redirects), 'redirects')
        print('NEXT: run classify, inspect, then activate. No live articles changed.')
    catalog.close()


def topic_roots():
    # Read the exact eight-group topic definitions used by the current game.
    source = (Path(__file__).resolve().parent.parent / 'lib/topics.ts').read_text(encoding='utf-8')
    rows = re.findall(r"\['([^']+)','([^']+)','([^']+)'\]", source)
    if len(rows) != 8:
        raise RuntimeError('Topic definitions changed; review importer mapping')
    result = []
    for group, group_name, children in rows:
        for i, entry in enumerate(children.split('|')):
            name, _, root = entry.partition('=')
            result.append({'id': f'topic:{group}:{i}', 'name': name,
                           'group': group, 'groupName': group_name,
                           'root': root or name})
    return result


def create_topic_map(catalog, max_depth):
    catalog.execute('CREATE TABLE IF NOT EXISTS topic_map(category text,topic text,group_id text,distance integer,path text,PRIMARY KEY(category,topic))')
    catalog.execute('DELETE FROM topic_map')
    catalog.commit()
    roots = topic_roots()
    catalog.execute('CREATE INDEX IF NOT EXISTS category_page_name ON category_pages(name)')
    for topic in tqdm(roots, desc='Mapping topic roots', unit='topic', **progress_options):
        visited = set()
        frontier = [(topic['root'], [topic['root']])]
        for depth in range(max_depth + 1):
            if not frontier:
                break
            nodes = []
            for name, path in frontier:
                if name not in visited:
                    nodes.append((name, path))
                    visited.add(name)
            frontier = []
            catalog.executemany('INSERT OR REPLACE INTO topic_map VALUES (?,?,?,?,?)',
                                [(name, topic['id'], topic['group'], depth, json.dumps(path, ensure_ascii=False))
                                 for name, path in nodes])
            if depth == max_depth:
                break
            for offset in range(0, len(nodes), 150):
                names = [name for name, _ in nodes[offset:offset + 150]]
                if not names:
                    continue
                placeholders = ','.join('?' for _ in names)
                query = f'SELECT l.category,p.name FROM links l JOIN category_pages p ON p.page_id=l.page_id WHERE l.category IN ({placeholders})'
                path_by_name = {name: path for name, path in nodes[offset:offset + 150]}
                for parent, child in catalog.execute(query, names):
                    if child not in visited:
                        frontier.append((child, path_by_name[parent] + [child]))
            catalog.commit()
    catalog.commit()
    return {row['id']: row for row in roots}


def topic_names(topics):
    return '、'.join(dict.fromkeys(t['name'] for t in topics)) or '待归类'


def match_categories(catalog, roots, categories):
    best = {}
    if categories:
        placeholders = ','.join('?' for _ in categories)
        for cat, topic_id, _, distance, path in catalog.execute(
            f'SELECT category,topic,group_id,distance,path FROM topic_map WHERE category IN ({placeholders})', categories):
            prev = best.get(topic_id)
            if prev is None or distance < prev[0]:
                best[topic_id] = (distance, json.loads(path), cat)
    # Mirror the live classifier: stop at the nearest category
    # ancestor depth, keeping every topic at that depth only.
    if best:
        nearest = min(value[0] for value in best.values())
        best = {key: value for key, value in best.items() if value[0] == nearest}
    found = []
    for topic_id, (distance, path, cat) in best.items():
        topic = roots[topic_id]
        # Existing game expects article category -> ancestors order.
        label_path = ['Category:' + cat] + ['Category:' + x for x in path[-2::-1]]
        found.append({'id': topic_id, 'name': topic['name'], 'group': topic['group'],
                      'groupName': topic['groupName'], 'path': label_path})
    return sorted(found, key=lambda t: (len(t['path']), t['id']))


def classify(directory, snapshot, max_depth):
    cache = directory / 'category-cache.sqlite3'
    if not cache.exists():
        raise RuntimeError('Missing category-cache.sqlite3; run stage first')
    catalog = sqlite3.connect(cache)
    roots = create_topic_map(catalog, max_depth)
    with db() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT state, article_count FROM wiki_snapshots WHERE id=%s", (snapshot,))
            item = cur.fetchone()
            if not item or item[0] not in ('staging', 'classified'):
                raise RuntimeError('Snapshot is not staged')
            cur.execute('CREATE TABLE IF NOT EXISTS wiki_stage_topic_updates(id bigint PRIMARY KEY,category text,data text)')
            cur.execute('TRUNCATE wiki_stage_topic_updates, wiki_stage_topics')
        conn.commit()
        last = 0
        processed = 0
        with tqdm(total=item[1], desc='Classifying articles', unit='article', **progress_options) as bar:
            while True:
                with conn.cursor() as cur:
                    cur.execute('SELECT id,data FROM wiki_stage_articles WHERE id>%s ORDER BY id LIMIT 1000', (last,))
                    batch = cur.fetchall()
                if not batch:
                    break
                updates, assignments = [], []
                for pageid, data in batch:
                    article = json.loads(data)
                    categories = article['categories']
                    article['topics'] = match_categories(catalog, roots, categories)
                    article['category'] = topic_names(article['topics'])
                    for t in article['topics']:
                        assignments.append((pageid, t['id'], t['group'], json.dumps(t['path'], ensure_ascii=False), len(t['path'])))
                    article['taxonomyVersion'] = 1
                    updates.append((pageid, article['category'], json.dumps(article, ensure_ascii=False)))
                with conn.cursor() as cur:
                    with cur.copy('COPY wiki_stage_topic_updates(id,category,data) FROM STDIN') as copy:
                        for row in updates:
                            copy.write_row(row)
                    with cur.copy('COPY wiki_stage_topics(page_id,topic,group_id,path,distance) FROM STDIN') as copy:
                        for row in assignments:
                            copy.write_row(row)
                conn.commit()
                last = batch[-1][0]
                processed += len(batch)
                bar.update(len(batch))
        with conn.cursor() as cur:
            cur.execute('UPDATE wiki_stage_articles a SET category=u.category,data=u.data,status=CASE WHEN u.category=\'待归类\' THEN \'unclassified\' ELSE a.status END FROM wiki_stage_topic_updates u WHERE u.id=a.id')
            cur.execute("UPDATE wiki_snapshots SET state='classified' WHERE id=%s", (snapshot,))
        conn.commit()
    catalog.close()
    print('Classified', processed, 'articles; no live tables changed.')


def activate(snapshot, confirm, min_articles):
    if snapshot != confirm:
        raise RuntimeError('Explicit --confirm SNAPSHOT is required for switching live word tables')
    safe = re.sub(r'[^a-zA-Z0-9_]', '_', snapshot)
    archive = 'wiki_articles_before_' + safe
    with db() as conn, tqdm(total=5, desc='Activating snapshot', unit='step', **progress_options) as bar:
        with conn.cursor() as cur:
            cur.execute("SELECT article_count,state FROM wiki_snapshots WHERE id=%s FOR UPDATE", (snapshot,))
            result = cur.fetchone()
            if not result or result[1] != 'classified' or result[0] < min_articles:
                raise RuntimeError(f'Snapshot not classified or too small: {result}')
            cur.execute('LOCK TABLE wiki_stage_articles IN SHARE ROW EXCLUSIVE MODE')
            cur.execute("""SELECT COUNT(*), COUNT(*) FILTER
                           (WHERE data::jsonb->>'snapshot' = %s) FROM wiki_stage_articles""", (snapshot,))
            if cur.fetchone() != (result[0], result[0]):
                raise RuntimeError('Staging rows do not match the classified snapshot; refusing activation')
            cur.execute('SELECT EXISTS(SELECT 1 FROM wiki_stage_topics)')
            if not cur.fetchone()[0]:
                raise RuntimeError('Snapshot has zero topic assignments; check category inputs before activation')
            cur.execute('SELECT to_regclass(%s)', (archive,))
            if cur.fetchone()[0] is not None:
                raise RuntimeError(f'Archive {archive} already exists; refusing to overwrite a rollback copy')
            cur.execute("SELECT value FROM settings WHERE key='rules'")
            rules_row = cur.fetchone()
            min_views = float(json.loads(rules_row[0]).get('minViews', 3)) if rules_row else 3.0
            bar.update(1)
            bar.set_description('Preserving referenced articles')
            # Keep old pages referenced by a player, vote, scheduled day or curated override.
            cur.execute("""
              INSERT INTO wiki_stage_articles
              SELECT a.id,a.title,a.canonical,a.data,a.category,a.chars,a.views,a.fetched,a.filter_version,
                     CASE WHEN a.featured>0 THEN 'active' ELSE 'archived' END,a.featured FROM articles a
              WHERE NOT EXISTS(SELECT 1 FROM wiki_stage_articles s WHERE s.id=a.id)
                AND (a.featured<>0 OR EXISTS(SELECT 1 FROM games g WHERE g.page_id=a.id)
                  OR EXISTS(SELECT 1 FROM daily d WHERE d.page_id=a.id)
                  OR EXISTS(SELECT 1 FROM votes v WHERE v.page_id=a.id)
                  OR EXISTS(SELECT 1 FROM comments c WHERE c.page_id=a.id)
                  OR EXISTS(SELECT 1 FROM aliases z WHERE z.page_id=a.id))
              ON CONFLICT(id) DO NOTHING
            """)
            cur.execute("""
              UPDATE wiki_stage_articles s SET featured=a.featured, views=a.views,
                 data=CASE WHEN a.views IS NOT NULL
                    THEN jsonb_set(s.data::jsonb,'{views}',to_jsonb(a.views))::text ELSE s.data END,
                 status=CASE WHEN e.page_id IS NOT NULL THEN 'excluded'
                    WHEN a.featured>0 THEN 'active'
                    WHEN a.views IS NOT NULL AND a.views>=%s AND s.status='pending_views' THEN 'active'
                    ELSE s.status END
              FROM articles a LEFT JOIN exclusions e ON e.page_id=a.id WHERE s.id=a.id
            """, (min_views,))
            bar.update(1)
            bar.set_description('Switching article tables')
            cur.execute(sql.SQL('ALTER TABLE articles RENAME TO {}').format(sql.Identifier(archive)))
            cur.execute('ALTER TABLE wiki_stage_articles RENAME TO articles')
            cur.execute('CREATE INDEX ON articles(status,id)')
            cur.execute('CREATE INDEX ON articles(title)')
            bar.update(1)
            bar.set_description('Updating topic assignments')
            cur.execute("DELETE FROM article_topics t USING articles a WHERE t.page_id=a.id AND a.status<>'archived'")
            cur.execute("""
              INSERT INTO article_topics(page_id,topic,group_id,path,distance)
              SELECT page_id,topic,group_id,path,distance FROM wiki_stage_topics WHERE TRUE
              ON CONFLICT(page_id,topic) DO UPDATE SET group_id=EXCLUDED.group_id,path=EXCLUDED.path,distance=EXCLUDED.distance
            """)
            bar.update(1)
            bar.set_description('Updating aliases and snapshot state')
            cur.execute("""
              INSERT INTO aliases(page_id,answer,normalized)
              SELECT a.id,r.source,r.normalized FROM wiki_stage_redirects r JOIN articles a ON a.canonical=r.target
              ON CONFLICT DO NOTHING
            """)
            cur.execute("UPDATE wiki_snapshots SET state='previous' WHERE state='active'")
            cur.execute("UPDATE wiki_snapshots SET state='active' WHERE id=%s", (snapshot,))
        conn.commit()
        bar.update(1)
    print(f'Activated snapshot {snapshot}. Previous articles preserved as {archive}.')
    print('Player tables, daily games, filters, editorial selections and scores were retained.')


def repair_categories(directory, snapshot, max_depth):
    """Backfill active snapshot rows whose source categories and assignments are empty."""
    if directory.name != snapshot:
        raise ValueError('Use the active YYYY-MM snapshot and its matching month directory')
    compressed, category_file, *targets = verify_local(directory)
    with tempfile.TemporaryDirectory(dir=directory) as work, db() as conn:
        catalog = category_catalog(category_file, Path(work) / 'repair.sqlite3', *targets)
        try:
            catalog.executemany('INSERT OR IGNORE INTO category_pages VALUES (?,?)',
                                ((pageid, title.split(':', 1)[-1].replace('_', ' '))
                                 for ns, title, pageid, *_ in wiki_pages(compressed) if ns == 14))
            roots = create_topic_map(catalog, max_depth)
            with conn.cursor() as cur:
                cur.execute("SELECT state FROM wiki_snapshots WHERE id=%s FOR SHARE", (snapshot,))
                if cur.fetchone() != ('active',):
                    raise ValueError('Snapshot is not active')
                cur.execute('CREATE TEMP TABLE repair(id bigint PRIMARY KEY, patch jsonb, label text) ON COMMIT DROP')
                with conn.cursor(name='missing_categories') as reader:
                    reader.execute("""SELECT id FROM articles a WHERE data::jsonb->>'snapshot'=%s
                        AND data::jsonb->'categories'='[]'::jsonb
                        AND NOT EXISTS(SELECT 1 FROM article_topics t WHERE t.page_id=a.id)""", (snapshot,))
                    # FETCH before COPY; the same connection cannot run a query during COPY.
                    matched = 0
                    recovered = 0
                    while batch := reader.fetchmany(1000):
                        with cur.copy('COPY repair(id,patch,label) FROM STDIN') as copy:
                            for (pageid,) in batch:
                                cats = [r[0] for r in catalog.execute('SELECT category FROM links WHERE page_id=?', (pageid,))]
                                if not cats:
                                    continue
                                topics = match_categories(catalog, roots, cats)
                                label = topic_names(topics)
                                patch = dict(categories=cats, topics=topics, category=label, taxonomyVersion=1)
                                copy.write_row((pageid, json.dumps(patch, ensure_ascii=False), label))
                                matched += bool(topics)
                                recovered += 1
                if recovered and not matched:
                    raise ValueError('No topic matches; live rows were not changed')
                cur.execute('LOCK TABLE articles, article_topics IN SHARE ROW EXCLUSIVE MODE')
                cur.execute("""DELETE FROM repair r WHERE NOT EXISTS(
                    SELECT 1 FROM articles a WHERE a.id=r.id AND a.data::jsonb->>'snapshot'=%s
                    AND a.data::jsonb->'categories'='[]'::jsonb)
                    OR EXISTS(SELECT 1 FROM article_topics t WHERE t.page_id=r.id)""", (snapshot,))
                cur.execute("""UPDATE articles a SET data=(a.data::jsonb || r.patch)::text, category=r.label,
                    status=CASE WHEN a.status='unclassified' AND jsonb_array_length(r.patch->'topics')>0
                                THEN 'pending_views' ELSE a.status END
                    FROM repair r WHERE a.id=r.id""")
                updated = cur.rowcount
                cur.execute("""INSERT INTO article_topics(page_id,topic,group_id,path,distance)
                    SELECT r.id,t->>'id',t->>'group',(t->'path')::text,jsonb_array_length(t->'path')
                    FROM repair r CROSS JOIN LATERAL jsonb_array_elements(r.patch->'topics') AS t""")
                print('Restored raw categories for', updated, 'articles;', cur.rowcount, 'topic assignments.')
        finally:
            catalog.close()


def repair_summary_batch(conn, pages, snapshot, apply=False):
    """Patch only summaries, preserving concurrently edited metadata and players."""
    with conn.transaction(), conn.cursor() as cur:
        cur.execute('SELECT id,data FROM articles WHERE id=ANY(%s)', ([p[0] for p in pages],))
        existing = {row[0]: json.loads(row[1]) for row in cur.fetchall()}
        changed = 0
        for pageid, revision, text in pages:
            current = existing.get(pageid)
            if (not current or current.get('snapshot') != snapshot
                    or int(current.get('revision') or 0) != revision
                    or current.get('textVersion') == TEXT_VERSION):
                continue
            patch = json.dumps({'summary': extract_summary(text), 'textVersion': TEXT_VERSION}, ensure_ascii=False)
            if apply:
                cur.execute("""UPDATE articles SET data=(data::jsonb || %s::jsonb)::text
                    WHERE id=%s AND data::jsonb->>'snapshot'=%s
                    AND data::jsonb->>'revision'=%s
                    AND data::jsonb->>'summary' IS NOT DISTINCT FROM %s
                    AND data::jsonb->>'textVersion' IS DISTINCT FROM %s""",
                    (patch, pageid, snapshot, str(revision), current.get('summary'), str(TEXT_VERSION)))
                changed += cur.rowcount
            else:
                changed += 1
        return changed


def repair_summaries(directory, snapshot, apply=False):
    """Stream the original local snapshot; resumable, 200 articles per transaction."""
    compressed, *_ = verify_local(directory)
    count, pages = 0, []
    with db() as conn:
        for ns, title, pageid, redirect, revid, text in wiki_pages(compressed):
            if ns != 0 or redirect or not pageid:
                continue
            pages.append((pageid, int(revid or 0), text))
            if len(pages) >= 200:
                count += repair_summary_batch(conn, pages, snapshot, apply)
                pages.clear()
        if pages:
            count += repair_summary_batch(conn, pages, snapshot, apply)
    print('Updated' if apply else 'Would update', count, 'article summaries.')
    if not apply:
        print('Dry run only. Add --apply to save; player tables and article eligibility are unchanged.')


def automatic(directory, max_depth, should_activate):
    """Operate on the newest local YYYY-MM directory; never access the Internet."""
    if not directory.is_dir():
        print('No manually downloaded wiki snapshots yet:', directory)
        return
    folders = sorted(
        (p for p in directory.iterdir()
         if p.is_dir() and re.fullmatch(r'20\d{2}-(0[1-9]|1[0-2])', p.name)),
        key=lambda p: p.name)
    if not folders:
        print('No month folders found in:', directory)
        return
    target = folders[-1]
    snapshot = target.name
    with db() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT state FROM wiki_snapshots WHERE id=%s", (snapshot,))
            row = cur.fetchone()
            state = row[0] if row else None
            if state == 'active':
                print('Already active:', snapshot)
                return
            staged_snapshot = None
            if state == 'classified':
                cur.execute("SELECT data::jsonb->>'snapshot' FROM wiki_stage_articles LIMIT 1")
                entry = cur.fetchone()
                staged_snapshot = entry[0] if entry else None
    if state != 'classified' or staged_snapshot != snapshot:
        # stage() verifies the checksums before any staging tables are changed.
        stage(target, snapshot)
        classify(target, snapshot, max_depth)
    else:
        print('Already classified:', snapshot)
    if should_activate:
        # Prevent activation if downloaded archives disappeared or were replaced
        # since the previous classification run.
        if state == 'classified' and staged_snapshot == snapshot:
            verify_local(target)
        activate(snapshot, snapshot, 10000)
    else:
        print('Prepared; activation pending. Review, then run activate with --confirm.')


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    sub = ap.add_subparsers(dest='action', required=True)
    for action in ('check', 'stage', 'classify', 'repair-categories', 'repair-summaries'):
        p = sub.add_parser(action)
        p.add_argument('--directory', type=Path, default=Path('wiki-dumps'))
        if action != 'check':
            p.add_argument('--snapshot', required=True)
        if action == 'stage':
            p.add_argument('--max-pages', type=int, help='TEST ONLY: stop after N eligible pages')
        if action == 'repair-summaries':
            p.add_argument('--apply', action='store_true', help='Write summaries; otherwise preview the count only')
        if action in ('classify', 'repair-categories'):
            p.add_argument('--max-depth', type=int, default=7)
    p = sub.add_parser('activate')
    p.add_argument('--snapshot', required=True)
    p.add_argument('--confirm', required=True)
    p.add_argument('--min-articles', type=int, default=10000)
    p = sub.add_parser('auto')
    p.add_argument('--directory', type=Path, default=Path('wiki-dumps'),
                   help='Parent directory containing manually downloaded YYYY-MM folders')
    p.add_argument('--max-depth', type=int, default=7)
    p.add_argument('--activate', action='store_true', help='Also replace the live word pool after validation')
    args = ap.parse_args()
    if args.action == 'check':
        verify_local(args.directory)
    elif args.action == 'stage':
        stage(args.directory, args.snapshot, args.max_pages)
    elif args.action == 'classify':
        classify(args.directory, args.snapshot, args.max_depth)
    elif args.action == 'repair-categories':
        repair_categories(args.directory, args.snapshot, args.max_depth)
    elif args.action == 'repair-summaries':
        repair_summaries(args.directory, args.snapshot, args.apply)
    elif args.action == 'activate':
        activate(args.snapshot, args.confirm, args.min_articles)
    elif args.action == 'auto':
        automatic(args.directory, args.max_depth, args.activate)


if __name__ == '__main__':
    main()
