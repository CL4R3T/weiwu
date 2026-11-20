import json,urllib.request,urllib.parse,re,html
from pathlib import Path
p=Path('data/wiki.json');rows=json.loads(p.read_text())
q=urllib.parse.urlencode({'action':'parse','text':'\n\nQZX\n\n'.join(r['title'] for r in rows),'contentmodel':'wikitext','prop':'text','format':'json','variant':'zh-hant','disablelimitreport':'1'})
url='https://zh.wikipedia.org/w/api.php?'+q
with urllib.request.urlopen(urllib.request.Request(url,headers={'User-Agent':'ZiliCangmi/1.0 (educational game)'}),timeout=30) as res: j=json.load(res)
text=html.unescape(re.sub('<[^>]+>','',j['parse']['text']['*']))
converted=[x.strip() for x in text.split('QZX')]
assert len(converted)==len(rows),(len(converted),len(rows))
for r,t in zip(rows,converted):
 if len(t)>len(r['title'])*2: raise ValueError('Unexpected conversion')
 r['traditional']=t
 r['aliases']=list(dict.fromkeys(r['aliases']+[t]))
p.write_text(json.dumps(rows,ensure_ascii=False,indent=2))
print('Added traditional aliases to',len(rows),'articles')
