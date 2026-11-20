import urllib.request,urllib.parse,json,time
from pathlib import Path
sources={'level2':'Wikipedia:基礎條目/第二級','level3':'Wikipedia:基礎條目/英語維基百科第三級','level4':'Wikipedia:基礎條目/第四級','level5':'Wikipedia:基礎條目/第五級','featured':'Wikipedia:典范条目','good':'Wikipedia:优良条目','unusual':'Wikipedia:維基誌異'}
output={}
for source,root in sources.items():
 try:
  p={'action':'query','titles':root,'prop':'links','pllimit':200,'plnamespace':'0|4','redirects':1,'format':'json'}
  u='https://zh.wikipedia.org/w/api.php?'+urllib.parse.urlencode(p)
  j=json.load(urllib.request.urlopen(urllib.request.Request(u,headers={'User-Agent':'ZiliCangmi/1.0 (educational Wikipedia table-of-contents game)'}),timeout=22))
  pages=list(j.get('query',{}).get('pages',{}).values());links=[l for p in pages for l in p.get('links',[])]; titles=[l['title'] for l in links if l['ns']==0]; children=[l['title'] for l in links if l['ns']==4 and (l['title'].startswith(root+'/') or source=='unusual' and l['title'].startswith(('Wikipedia:维基志异/','Wikipedia:維基誌異/')))]
  output[source]={'titles':titles,'children':children,'cursor':j.get('continue'),'root':root};Path('data/source-seed.json').write_text(json.dumps(output,ensure_ascii=False));print(source,len(titles),len(children),bool(j.get('continue')),flush=True)
 except Exception as e:print(source,str(e),flush=True)
 time.sleep(3)
