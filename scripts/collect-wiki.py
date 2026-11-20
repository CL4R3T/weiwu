import urllib.request, urllib.parse, json, re, html, concurrent.futures, time
from pathlib import Path
categories = {
'思想与社会':'忒修斯之船|薛定谔的猫|中文房间|电车难题|囚徒困境|蝴蝶效应|费米悖论|奥卡姆剃刀|麦克斯韦妖|无限猴子定理|图灵测试|幸存者偏差|安慰剂效应|认知失调|马斯洛需求层次理论|邓宁-克鲁格效应|乌托邦|公地悲剧|斯德哥尔摩综合征',
'科学与自然':'旅行者金唱片|康威生命游戏|黑洞|暗物质|量子纠缠|熵|超导现象|莫比乌斯带|克莱因瓶|分形|混沌理论|圆周率|黄金分割率|斐波那契数|板块构造论|大陆漂移说|寒武纪大爆发|白垩纪—古近纪灭绝事件|恐龙|鸭嘴兽|水熊虫|极光|球状闪电|光合作用|CRISPR',
'历史与文明':'罗塞塔石碑|图坦卡蒙|特洛伊木马|巴别塔|空中花园|丝绸之路|黑死病|工业革命|文艺复兴|大航海时代|曼哈顿计划|切尔诺贝利核事故|阿波罗11号|百年战争|铁幕',
'文化与生活':'火星文|达芬奇|蒙娜丽莎|清明上河图|格尔尼卡|百年孤独|小王子|一九八四|三体|楚门的世界|俄罗斯方块|魔方|狼人杀|密室逃脱|佛跳墙|臭豆腐|螺蛳粉|咖啡|巧克力|爵士乐|摇滚乐|赛博朋克|蒸汽朋克|后室|都市传说|食人'
}
aliases={'电车难题':['有轨电车难题','电车问题'],'达芬奇':['达·芬奇','列奥纳多·达·芬奇','列奥纳多达芬奇'],'一九八四':['1984'],'康威生命游戏':['生命游戏'],'薛定谔的猫':['薛定谔猫'],'邓宁-克鲁格效应':['达克效应','邓宁克鲁格效应'],'黄金分割率':['黄金分割'],'旅行者金唱片':['旅行者号金唱片']}
def clean(s): return html.unescape(re.sub('<[^>]+>','',s)).strip()
def get(pair):
 cat,title=pair
 url='https://zh.wikipedia.org/w/api.php?'+urllib.parse.urlencode({'action':'parse','page':title,'prop':'tocdata|displaytitle|revid','format':'json','variant':'zh-hans','redirects':'1'})
 try:
  with urllib.request.urlopen(urllib.request.Request(url,headers={'User-Agent':'ZiliCangmi/1.0 (educational Wikipedia table-of-contents game)'}),timeout=24) as res: p=json.load(res)['parse']
  sections=[{'text':clean(s['line']),'level':s['tocLevel'],'number':s['number']} for s in p['tocdata']['sections']]
  if len(sections)<4: return None
  return {'id':str(p['pageid']),'title':clean(p['displaytitle']),'canonical':p['title'],'aliases':list(set([title,p['title'],clean(p['displaytitle'])]+aliases.get(title,[]))),'category':cat,'sections':sections,'revision':p.get('revid'),'fetchedAt':'2026-11-16'}
 except Exception as e: print('SKIP',title,str(e),flush=True)
pairs=[(cat,t) for cat,ts in categories.items() for t in ts.split('|')]
rows=json.loads(Path('data/wiki.json').read_text()) if Path('data/wiki.json').exists() else []
existing={alias for r in rows for alias in r['aliases']}
for pair in pairs:
 if pair[1] in existing: continue
 time.sleep(3)
 row=get(pair)
 if row:
  rows.append(row)
  Path('data/wiki.json').write_text(json.dumps(rows,ensure_ascii=False,indent=2))
  print('ADDED',pair[1],len(rows),flush=True)
print('SAVED',len(rows),'articles',sum(len(x['sections']) for x in rows),'headings',flush=True)
