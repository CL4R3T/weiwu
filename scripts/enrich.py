import urllib.request,urllib.parse,json,re,html,time,concurrent.futures,datetime
from pathlib import Path
UA={'User-Agent':'ZiliCangmi/1.0 (educational Wikipedia table-of-contents game)'}
def get(u):
 return json.load(urllib.request.urlopen(urllib.request.Request(u,headers=UA),timeout=25))
def wiki(p):return get('https://zh.wikipedia.org/w/api.php?'+urllib.parse.urlencode({'format':'json',**p}))
def enrich(a):
 try:
  j=wiki({'action':'query','pageids':a['id'],'prop':'extracts|categories|info','explaintext':'1','cllimit':'max','variant':'zh-hans'})
  p=next(iter(j['query']['pages'].values()));t=p.get('extract','');cats=[c['title'] for c in p.get('categories',[])]; end=datetime.datetime.now(datetime.timezone.utc).date()-datetime.timedelta(days=1);start=end-datetime.timedelta(days=29)
  u='https://wikimedia.org/api/rest_v1/metrics/pageviews/per-article/zh.wikipedia/all-access/user/'+urllib.parse.quote(p['title'],safe='')+'/daily/'+start.strftime('%Y%m%d')+'00/'+end.strftime('%Y%m%d')+'00'
  v=get(u);values=sorted(i['views'] for i in v['items']); median=values[len(values)//2] if len(values)>=20 else None
  a.update(chars=len(re.sub(r'\s','',t)),views=median,summary=t.split('\n\n')[0][:600],categories=cats,viewWindow={'start':str(start),'end':str(end)},fetchedAt=str(end+datetime.timedelta(days=1)))
  return a
 except Exception as e:print('skip',a['title'],e,flush=True)
x=json.load(open('data/wiki.json')); output=[]
with concurrent.futures.ThreadPoolExecutor(max_workers=3) as ex:
 for a in ex.map(enrich,x[:36]):
  if a:output.append(a);Path('data/seed.json').write_text(json.dumps(output,ensure_ascii=False));print('saved',a['title'],a['chars'],a['views'],flush=True)
print('complete',len(output),flush=True)
