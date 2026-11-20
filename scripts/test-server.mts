import {DatabaseSync} from 'node:sqlite';
import {readFileSync,readdirSync} from 'node:fs';
import assert from 'node:assert/strict';
import {handle} from '../lib/server/service';
import {hash,password,now,day,uid} from '../lib/server/core';
import {reason,SOURCES} from '../lib/server/wiki';
import {DEFAULTS} from '../lib/server/core';
const sql=new DatabaseSync(':memory:');for(const f of readdirSync('drizzle').filter(f=>f.endsWith('.sql')).sort())sql.exec(readFileSync('drizzle/'+f,'utf8'));
class Statement{sql:string;args:any[]=[];constructor(s:string){this.sql=s;}bind(...a:any[]){this.args=a;return this}async first(){return sql.prepare(this.sql).get(...this.args)||null}async all(){return {results:sql.prepare(this.sql).all(...this.args)}}async run(){return {meta:sql.prepare(this.sql).run(...this.args)}}}
const db={prepare:(s:string)=>new Statement(s),async batch(ss:Statement[]){sql.exec('BEGIN');try{const out=[];for(const s of ss)out.push(await s.run());sql.exec('COMMIT');return out;}catch(e){sql.exec('ROLLBACK');throw e}}};
const cookie:Record<string,string>={};const env={SUPER_ADMIN_ID:'test-super-owner',SUPER_ADMIN_USERNAME:'owner',SUPER_ADMIN_SALT:'owner-test-salt',SUPER_ADMIN_HASH:await password('owner-test-password','owner-test-salt')};
async function call(client:string,action:string,data?:any,headers:any={},query:any={}){const url='https://game.test/api/v1?'+new URLSearchParams({action,...query});const r=await handle(new Request(url,{method:data?'POST':'GET',headers:{'cf-connecting-ip':client,...(cookie[client]?{cookie:cookie[client]}:{}),...(data?{'Content-Type':'application/json',origin:'https://game.test'}:{}),...headers},body:data?JSON.stringify(data):undefined}),db,env);if(r.headers.get('set-cookie'))cookie[client]=r.headers.get('set-cookie')!.split(';')[0];return {status:r.status,...await r.json() as any};}
async function register(c:string){const id=uid();sql.prepare('INSERT INTO captchas VALUES(?,?,?)').run(id,await hash(id+'ABCDE'),now()+60000);return call(c,'register',{username:c,password:'test-password-123',nickname:c,captchaId:id,captcha:'ABCDE'});}
const seed:any=JSON.parse(readFileSync('data/seed.json','utf8'));
assert.equal(reason({...seed[0],chars:5},DEFAULTS),'正文不足 800 字符');assert.match(reason({...seed[0],sections:[{level:1,text:'历史'},{level:1,text:'参考资料'},{level:2,text:'文献'}]},DEFAULTS)||'',/没有含二级/);assert.match(reason({...seed[0],categories:['中国共产党']},DEFAULTS)||'',/敏感/);assert.match(reason({...seed[0],views:0},DEFAULTS)||'',/浏览量/);
// Existing fixtures use an offline category graph; no remote requests during role tests.
for(const a of seed)for(const c of a.categories||[])sql.prepare('INSERT OR IGNORE INTO category_nodes VALUES(?,?,?)').run(c,'[]',now());
const initial=await call('guest1','init');assert.equal(initial.status,200);assert.equal(initial.user,null);assert.equal(sql.prepare('SELECT COUNT(*) n FROM daily').get()!.n,8);assert.equal((await call('guest1','start',{mode:'random',sources:['level3']})).status,401);
const guest=await call('guest1','start',{mode:'daily',date:day()});assert.equal(guest.status,200);assert(!guest.result);assert(!('pageId'in guest));const again=await call('guest1','start',{mode:'daily',date:day()});assert.equal(again.id,guest.id);assert.equal(again.started,guest.started);
const pageId=(sql.prepare('SELECT page_id FROM games WHERE id=?').get(guest.id) as any).page_id;
assert.equal((await call('guest1','discussion',undefined,{}, {pageId})).status,403);assert.equal((await call('guest2','reveal',{id:guest.id})).status,404);
assert.equal((await register('alice')).status,200);assert.equal((await register('bobby')).status,200);const ownerCaptcha=uid();sql.prepare('INSERT INTO captchas VALUES(?,?,?)').run(ownerCaptcha,await hash(ownerCaptcha+'ABCDE'),now()+60000);assert.equal((await call('owner','login',{username:'owner',password:'owner-test-password',captchaId:ownerCaptcha,captcha:'ABCDE'})).user.role,'super');
assert.equal((await call('alice','adminOverview')).status,403);assert.equal((await call('alice','claimOwner',{})).status,404);assert.equal((await call('owner','claimOwner',{})).status,404);assert.equal(sql.prepare("SELECT COUNT(*) n FROM users WHERE role='super'").get()!.n,1);
const ag=await call('alice','start',{mode:'daily',date:day()});const correct=(sql.prepare('SELECT title FROM articles WHERE id=?').get(pageId) as any).title;const won=await call('alice','guess',{id:ag.id,answer:correct});assert.equal(won.state,'won');assert.equal(won.guessCount,1);const twice=await call('alice','guess',{id:ag.id,answer:correct});assert.equal(twice.guessCount,1);
assert.equal((await call('alice','vote',{pageId,value:1})).status,200);assert.equal((await call('alice','vote',{pageId,value:1})).status,200);assert.equal(sql.prepare('SELECT COUNT(*) n FROM votes').get()!.n,1);assert.equal((await call('bobby','vote',{pageId,value:1})).status,403);
assert.equal((await call('alice','comment',{pageId,text:'<script>alert(1)</script>'})).status,200);const discussion=await call('alice','discussion',undefined,{}, {pageId});assert.equal(discussion.comments.length,1);
assert.equal((await call('alice','propose',{pageId,answer:'一个可接受别名'})).status,200);const proposals=await call('owner','adminProposals');assert.equal((await call('owner','adminReview',{id:proposals.proposals[0].id,approve:true})).status,200);const bg=await call('bobby','start',{mode:'daily',date:day()});assert.equal((await call('bobby','guess',{id:bg.id,answer:'一个可接受别名'})).state,'won');
const alice=(sql.prepare("SELECT id FROM users WHERE username='alice'").get() as any).id;assert.equal((await call('owner','adminModerate',{userId:alice,field:'nickname',reason:'请修改'})).status,200);assert.equal((await call('alice','comment',{pageId,text:'不能发'})).status,403);assert.equal((await call('alice','profileEdit',{nickname:'alice',avatar:'🌫️'})).status,400);assert.equal((await call('alice','profileEdit',{nickname:'新名字',avatar:'🌱'})).status,200);assert.equal((await call('owner','adminRole',{userId:alice,role:'admin'})).status,200);assert.equal((await call('alice','adminOverview')).status,200);assert.equal((await call('alice','adminRole',{userId:alice,role:'super'})).status,403);
assert.equal((await call('owner','adminDaily',{date:day(),article:String(pageId)})).status,400);assert.equal((await call('owner','adminDaily',{date:day(1),article:String(pageId)})).status,200);
assert.equal((await call('alice','leaderboard',undefined,{}, {type:'rate'})).rows.length,0);assert.equal((await call('alice','leaderboard',undefined,{}, {type:'count'})).rows.length,2);
// Random scope is single-choice and remains locked across reload/API calls.
assert.equal((await register('scopeuser')).status,200);
for(const source of ['level2','level3']){sql.prepare('INSERT OR IGNORE INTO pool VALUES(?,?)').run(source,correct);sql.prepare('INSERT OR IGNORE INTO source_jobs VALUES(?,?,NULL,1,?)').run(source,SOURCES[source].root,now());}
assert.equal((await call('scopeuser','start',{mode:'random',sources:['level2','level3']})).status,400);
const scoped=await call('scopeuser','start',{mode:'random',sources:['level2'],skip:false});assert.equal(scoped.source,'level2');
assert.equal((await call('scopeuser','init')).activeRandom.source,'level2');
assert.equal((await call('scopeuser','start',{mode:'random',sources:['level3']})).status,409);
assert.equal((await call('scopeuser','start',{mode:'random',sources:['level2'],next:true})).status,409);
assert.equal((await call('scopeuser','start',{mode:'random',sources:['level2']})).id,scoped.id);
await call('scopeuser','reveal',{id:scoped.id});assert.equal((await call('scopeuser','start',{mode:'random',sources:['level3'],skip:false})).source,'level3');
const cross=await call('alice','comment',{pageId,text:'csrf'},{origin:'https://evil.test'});assert.equal(cross.status,403);
assert.equal((await call('owner','adminBlock',{pageId,title:correct,reason:'测试'})).status,200);assert.equal((sql.prepare('SELECT COUNT(*) n FROM daily WHERE date>? AND page_id=?').get(day(),pageId) as any).n,0);
// CAPTCHA is expiring and single-use, and no password-reset action is exposed.
const cap=await call('fresh','captcha');assert.equal(cap.status,200);assert(cap.image.startsWith('data:image/png;base64,'));
const cid=uid();sql.prepare('INSERT INTO captchas VALUES(?,?,?)').run(cid,await hash(cid+'ABCDE'),now()+60000);
const invalid=await call('fresh','register',{username:'fresh',password:'secret-pass-123',captchaId:cid,captcha:'WRONG'});assert.equal(invalid.status,400);
const replay=await call('fresh','register',{username:'fresh',password:'secret-pass-123',captchaId:cid,captcha:'ABCDE'});assert.equal(replay.status,400);
assert.equal((await call('alice','changePassword',{password:'changed'})).status,404);
console.log('PASS: filters; guest/user/admin/super permissions; stable daily timer; ownership; spoiler protection; correct answers; idempotent votes; comments; aliases; moderation; daily scheduling; leaderboards; CSRF; blocklist.');
// Daily restoration is read-only and reveals only completed games.
const restored=await call('alice','dailyState',undefined,{}, {date:day()});assert.equal(restored.game.id,ag.id);assert.equal(restored.game.state,'won');assert.deepEqual(restored.game.sections,restored.game.result.sections);assert.equal(restored.game.started,ag.started);
assert.equal((await call('freshday','dailyState',undefined,{}, {date:day()})).game,null);
const {match,hints}=await import('../lib/game');
assert(match({...seed[0],title:'水星（行星）',canonical:'水星 (行星)',aliases:[]},'水星'));assert(!match({...seed[0],title:'水星（行星）',canonical:'水星 (行星)',aliases:[]},'行星'));
assert.equal(hints(seed[0],0).length,0);assert.equal(hints(seed[0],1).length,1);assert.match(hints({...seed[0],topics:[{name:'哲学'}]},1)[0],/^二级分类：哲学$/);assert.match(hints(seed[0],2)[1],/^字数：/);assert.equal(hints(seed[0],2).length,2);assert.equal(hints(seed[0],3).length,3);
assert.equal(reason({...seed[0],title:'第三十届电影节'},DEFAULTS),'届次类条目');assert.equal(reason({...seed[0],title:'第30屆電影節'},DEFAULTS),'届次类条目');
// Check source metadata and filtering on both player views.
const history=await call('scopeuser','profile',undefined,{}, {filter:'level2'});assert.equal(history.records.length,1);assert.equal(history.records[0].source,'level2');
const sh=await call('owner','adminPlayer',undefined,{}, {id:history.user.id,filter:'level2'});assert.equal(sh.records[0].source,'level2');
// Independent pages, role filters, voted article tabs, and SQL-backed category filter.
for(let i=0;i<24;i++)sql.prepare("INSERT INTO users(id,username,password_hash,salt,nickname,role,created_at) VALUES(?,?, 'test','test',?,'user',?)").run('paging'+i,'paging'+i,'分页'+i,now()+i);
const users1=await call('owner','adminUsers',undefined,{}, {q:'paging'}),users2=await call('owner','adminUsers',undefined,{}, {q:'paging',offset:'20'});assert.equal(users1.users.length,20);assert.equal(users1.total,24);assert(users1.hasMore);assert.equal(users2.users.length,4);assert(!users2.hasMore);assert(!users2.users.some((u:any)=>users1.users.some((v:any)=>v.id===u.id)));
assert.equal((await call('owner','adminUsers',undefined,{}, {filter:'super'})).users.length,1);
const likes=await call('owner','adminArticles',undefined,{}, {tab:'likes'});assert.equal(likes.status,200);assert.equal(likes.articles[0].likes,1);assert(likes.articles[0].sources.includes('level2'));
assert.equal((await call('owner','adminArticles',undefined,{}, {tab:'dislikes'})).articles.length,0);
assert.equal((await call('owner','adminArticles',undefined,{}, {tab:'excluded'})).exclusions.length>0,true);
assert.equal((await call('owner','adminArticles',undefined,{}, {filter:'不存在领域'})).articles.length,0);
for(let i=0;i<23;i++)sql.prepare('INSERT INTO comments VALUES(?,?,?,?,?,0)').run('pagingcomment'+i,alice,pageId,'分页评论'+i,now()+i);
const cp=await call('alice','discussion',undefined,{}, {pageId,offset:'20'});assert.equal(cp.comments.length,4);assert(!cp.hasMore);assert.equal((await call('owner','adminComments',undefined,{}, {q:'分页评论'})).total,23);
// Remote fixtures cover redlinks, numeric titles, simplified redirects, parse deletion races and silent continuation.
const {article,choose}=await import('../lib/server/wiki');const originalFetch=globalThis.fetch;const requests:URL[]=[];let onlyExcluded=false;
globalThis.fetch=async(input:any)=>{const u=new URL(String(input));requests.push(u);const p=u.searchParams;
 if(u.hostname==='wikimedia.org')return Response.json({items:Array.from({length:30},()=>({views:50}))});
 if(p.get('action')==='query'&&p.get('list')==='random')return Response.json({query:{random:onlyExcluded?[{id:8801,title:'短小页面'}]:[{id:8801,title:'短小页面'},{id:8802,title:'合格页面'}]}});
 if(p.get('action')==='query'&&p.get('prop'))return Response.json({query:{pages:{[p.get('pageids')!]:{extract:'正文'.repeat(600)}}}});
 if(p.get('action')==='query'){if(p.get('titles')==='不存在页面')return Response.json({query:{pages:{'-1':{missing:'',ns:0,title:'不存在页面'}}}});let id=p.get('titles')==='0'?8800:p.get('titles')==='移动中'?8803:Number(p.get('pageids')||8802);return Response.json({query:{pages:{[id]:{pageid:id,ns:0,title:id===8800?'0':'合格页面'}}}});}
 if(p.get('action')==='parse'){const id=Number(p.get('pageid'));if(id===8803)return Response.json({error:{code:'missingtitle'}});return Response.json({parse:{pageid:id,title:id===8800?'0':id===8801?'短小页面':'合格页面',displaytitle:id===8800?'0':id===8801?'短小页面':'合格页面',revid:1,categories:[],tocdata:{sections:id===8801?[]:[{line:'历史',number:'1',tocLevel:1},{line:'沿革',number:'1.1',tocLevel:2}]}}});}
 return Response.json({query:{pages:{'-1':{missing:''}}}});
};
try{
 assert.equal(await article(db,'不存在页面',true),null);assert.equal(await article(db,'移动中',true),null);
 const zero=await article(db,'0',true);assert.equal(zero.id,'8800');assert(requests.some(u=>u.searchParams.get('titles')==='0'));assert(!requests.some(u=>u.searchParams.get('pageid')==='0'));
 const ocean=await choose(db,'ocean',[],null,false);assert.equal(ocean.id,'8802');assert(sql.prepare('SELECT page_id FROM exclusions WHERE page_id=8801').get());
 onlyExcluded=true;assert.equal(await choose(db,'ocean',[],null,false),null);onlyExcluded=false;assert.equal((await choose(db,'ocean',[],null,false)).id,'8802');
 const scopeGame=(await call('scopeuser','start',{mode:'random',sources:['level3'],skip:false}));
 for(let i=1;i<=3;i++){const wrong=await call('scopeuser','guess',{id:scopeGame.id,answer:'错误答案'+i});assert.equal(wrong.status,200);assert.equal(wrong.hints.length,i);assert(!wrong.result);}
}finally{globalThis.fetch=originalFetch}
console.log('PASS: restored daily; unmasked completed TOC; parentheses answers; progressive hints; source records; pagination/filtering; likes/dislikes tabs; redlinks/numeric titles; silent filtered candidate retry.');

// Official redirects, disambiguation, and category graph traversal.
const {officialAnswer}=await import('../lib/server/mediawiki');
const {classifyArticle,refreshTopic}=await import('../lib/server/topics');
const {TOPICS,TOPIC_GROUPS}=await import('../lib/topics');
assert.equal(TOPIC_GROUPS.length,8);
const philosophy=TOPICS.find(t=>t.name==='哲学')!;
let categoryPage=0;
globalThis.fetch=async(input:any)=>{const p=new URL(String(input)).searchParams;
 if(p.get('prop')==='pageprops'){
  if(p.get('titles')==='断网别名')throw new Error('network');
  if(p.get('titles')==='模糊别名')return Response.json({query:{pages:{9:{pageid:9,ns:0,pageprops:{disambiguation:''}}}}});
  if(p.get('titles')==='官方重定向')return Response.json({query:{redirects:[{from:'官方重定向',to:'合格页面'}],pages:{8802:{pageid:8802,ns:0,title:'合格页面'}}}});
  return Response.json({query:{pages:{'-1':{ns:0,missing:''}}}});
 }
 if(p.get('list')==='categorymembers'){
  categoryPage++;
  if(p.get('cmtitle')==='Category:哲学')return Response.json({query:{categorymembers:[{ns:14,title:'Category:专题子类',pageid:10}]}});
  return Response.json({query:{categorymembers:[{ns:14,title:'Category:哲学',pageid:11},{ns:0,title:'合格页面',pageid:8802}]}});
 }
 if(p.get('prop')==='categories|categoryinfo'){
  const pages=Object.fromEntries((p.get('titles')||'').split('|').map((title,i)=>[i,{title,ns:14,pageid:100+i,categories:(title==='Category:测试起点'?['Category:测试循环','Category:哲学']:title==='Category:测试循环'?['Category:测试起点']:[]).map(title=>({title}))}]));
  return Response.json({query:{pages}});
 }
 throw new Error('Unexpected fixture request '+p.toString());
};
try{
 assert.equal(await officialAnswer('官方重定向',8802),'correct');
 assert.equal(await officialAnswer('模糊别名',8802),'ambiguous');
 assert.equal(await officialAnswer('不存在',8802),'wrong');
 const classified=await classifyArticle(db,{...seed[0],id:'8802',topics:[],taxonomyVersion:0,categories:['Category:测试起点']});
 assert(classified.topics.some((t:any)=>t.id===philosophy.id));
 assert.deepEqual(classified.topics.find((t:any)=>t.id===philosophy.id).path,['Category:测试起点','Category:哲学']);
 assert.equal((await refreshTopic(db,philosophy.id)).complete,false);
 assert.equal((await refreshTopic(db,philosophy.id)).complete,true);
 assert.equal(sql.prepare('SELECT COUNT(*) n FROM topic_queue WHERE source=?').get(philosophy.id)!.n,2);
 assert.equal((await register('topicplayer')).status,200);
 const g=await call('topicplayer','start',{mode:'random',sources:[philosophy.id],skip:false});assert.equal(g.status,200);assert.equal(g.source,philosophy.id);assert(!g.result);assert.equal(g.hints.length,0);
 const ambiguous=await call('topicplayer','guess',{id:g.id,answer:'模糊别名'});assert(ambiguous.ambiguous);assert.equal(ambiguous.guessCount,0);assert.equal(ambiguous.state,'playing');
 const offline=await call('topicplayer','guess',{id:g.id,answer:'断网别名'});assert.equal(offline.status,503);
 const retry=await call('topicplayer','game',undefined,{}, {id:g.id});assert.equal(retry.guessCount,0);
 assert.equal((await call('topicplayer','start',{mode:'random',sources:['level3']})).status,409);
 const wrong=await call('topicplayer','guess',{id:g.id,answer:'不存在'});assert.deepEqual(wrong.hints,[`字数：${Array.from(seed[0].title).length}`]);
 const redirectWin=await call('topicplayer','guess',{id:g.id,answer:'官方重定向'});assert.equal(redirectWin.state,'won');assert.equal(redirectWin.guessCount,2);
 const topicHistory=await call('topicplayer','profile',undefined,{}, {filter:philosophy.id});assert.equal(topicHistory.records.length,1);assert.equal(topicHistory.records[0].source,philosophy.id);assert(topicHistory.domains.some((r:any)=>r.category==='人文与社会科学'));
 assert.equal((await call('topicplayer','profile',undefined,{}, {filter:philosophy.group})).records.length,1);
 const adminTopic=await call('owner','adminArticles',undefined,{}, {filter:philosophy.id});assert(adminTopic.articles.some((a:any)=>a.id===8802));
 assert.equal((await call('topicplayer','profileEdit',{nickname:'专题玩家',avatar:'🪼'})).status,200);
}finally{globalThis.fetch=originalFetch}
console.log('PASS: official eight groups; graph traversal/cycles; topic selection and source lock; exact topic/group history; redirect matching; ambiguous/no-network no-attempt consumption; new hints; extended emoji.');

// Radar: unknown categories excluded; fixed eight axes; repeated and ongoing games excluded.
const {recognitionAxes}=await import('../lib/recognition');
assert.equal(recognitionAxes([]).length,8);assert(recognitionAxes([]).every(x=>x.score===0));
const mixed=recognitionAxes([{category:'nature',total:3,won:2},{category:'unclassified',total:200,won:0}]);
assert.equal(mixed.find(x=>x.id==='nature')!.score,66.7);assert(mixed.find(x=>x.id==='nature')!.smallSample);assert(!mixed.some(x=>x.category==='待归类'));
assert.equal(recognitionAxes([{category:'nature',total:5,won:0}]).find(x=>x.id==='nature')!.score,0);
assert.equal(hints(seed[0],0,true).length,0);assert.deepEqual(hints(seed[0],1,true),[`字数：${Array.from(seed[0].title).length}`]);assert.equal(hints(seed[0],2,true)[1],`第一个字：${Array.from(seed[0].title)[0]}`);assert.equal(hints(seed[0],6,true).length,2);
const tg:any=sql.prepare("SELECT * FROM games WHERE user_id=(SELECT id FROM users WHERE username='topicplayer') LIMIT 1").get();
// Additional second-level classification within the same parent must not double-count.
sql.prepare('INSERT OR IGNORE INTO article_topics VALUES(?,?,?,?,?)').run(8802,'topic:humanities:1','humanities','[]',1);
sql.prepare('INSERT OR IGNORE INTO article_topics VALUES(?,?,?,?,?)').run(8802,'topic:nature:0','nature','[]',1);
const clone=(id:string,page:number,state:string,stamp:number)=>sql.prepare("INSERT INTO games(id,owner,user_id,page_id,mode,state,started,finished,guess_count,competitive,snapshot,source) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)").run(id,tg.owner,tg.user_id,page,'featured',state,stamp,state==='playing'?null:stamp+1000,6,0,tg.snapshot,null);
clone('radar-repeat',8802,'revealed',tg.started+10000);
clone('radar-unclassified',8800,'revealed',tg.started+10000);
clone('radar-playing',8804,'playing',tg.started+10000);
sql.prepare('INSERT OR IGNORE INTO article_topics VALUES(?,?,?,?,?)').run(8804,'topic:nature:0','nature','[]',1);
const radarProfile=await call('topicplayer','profile');assert.equal(radarProfile.domains.length,8);
for(const group of ['humanities','nature']){const axis=radarProfile.domains.find((x:any)=>x.id===group);assert.equal(axis.total,1);assert.equal(axis.won,1);assert.equal(axis.score,100);}
assert.equal(radarProfile.domains.find((x:any)=>x.id==='world').score,0);
const adminRadar=await call('owner','adminPlayer',undefined,{}, {id:tg.user_id});assert.deepEqual(adminRadar.domains,radarProfile.domains);
console.log('PASS: topic hint starts with length; eight-axis scoring; no unknown/ongoing/repeat contributions; multi-topic deduplication; sparse/zero scores; admin/player agreement.');

assert.equal(recognitionAxes([{category:'nature',total:4,won:4}]).find(x=>x.id==='nature')!.score,100);
assert.equal(recognitionAxes([{category:'nature',total:5,won:4}]).find(x=>x.id==='nature')!.score,80);

// Featured maintenance: real permissions, pagination, filtering, removal and selection.
assert.equal((await call('bobby','adminFeatured')).status,403);
assert.equal((await call('guest1','adminArticleDetail',undefined,{}, {id:pageId})).status,401);
assert.equal((await call('bobby','adminFeature',{article:String(pageId),remove:true})).status,403);
const featuredSeed=seed.find((a:any)=>!sql.prepare('SELECT page_id FROM exclusions WHERE page_id=?').get(Number(a.id)));
for(let i=0;i<24;i++){
 const a={...featuredSeed,id:String(9900+i),title:'精选测试'+i,canonical:'精选测试'+i};
 sql.prepare("INSERT INTO articles(id,title,canonical,data,category,chars,views,fetched,filter_version,status,featured) VALUES(?,?,?,?,?,?,?,?,?,'active',?)").run(Number(a.id),a.title,a.canonical,JSON.stringify(a),a.category,a.chars,a.views,now()+i,DEFAULTS.version,i%2?2:1);
 sql.prepare('INSERT INTO article_topics VALUES(?,?,?,?,?)').run(Number(a.id),'topic:nature:0','nature','[]',1);
}
const fp1=await call('owner','adminFeatured',undefined,{}, {q:'精选测试'}),fp2=await call('owner','adminFeatured',undefined,{}, {q:'精选测试',offset:'20'});
assert.equal(fp1.status,200);assert.equal(fp1.total,24);assert.equal(fp1.articles.length,20);assert(fp1.hasMore);assert.equal(fp2.articles.length,4);assert(!fp2.hasMore);
assert(!fp2.articles.some((a:any)=>fp1.articles.some((b:any)=>a.id===b.id)));
assert.equal((await call('owner','adminFeatured',undefined,{}, {q:'精选测试',kind:'auto'})).total,12);
assert.equal((await call('owner','adminFeatured',undefined,{}, {q:'精选测试',filter:'nature'})).total,24);
assert.equal((await call('owner','adminFeatured',undefined,{}, {q:'精选测试',filter:'world'})).total,0);
assert.equal((await call('owner','adminFeatured',undefined,{}, {q:'精选测试',filter:'topic:nature:0'})).total,24);
assert.equal((await call('owner','adminFeatured',undefined,{}, {kind:'invalid'})).status,400);
const featuredDetail=await call('owner','adminArticleDetail',undefined,{}, {id:'9900'});assert.equal(featuredDetail.title,'精选测试0');assert.deepEqual(featuredDetail.sections,featuredSeed.sections);assert.equal(featuredDetail.summary,featuredSeed.summary);
assert.equal((await call('alice','adminFeature',{article:'9900',remove:true})).status,200); // ordinary admin permitted
assert.equal((await call('owner','adminFeatured',undefined,{}, {q:'9900'})).total,0);
assert.equal((await call('owner','adminFeatured',undefined,{}, {q:'9900',kind:'removed'})).total,1);
assert.equal((await call('owner','adminFeature',{article:'9900'})).status,200);
assert.equal((await call('owner','adminFeature',{article:'9900'})).status,200); // idempotent
assert.equal((await call('owner','adminFeatured',undefined,{}, {q:'9900'})).total,1);
// A blocked featured entry remains removable without a Wiki call or filter bypass.
sql.prepare("UPDATE articles SET status='excluded' WHERE id=9900").run();
sql.prepare("INSERT INTO exclusions VALUES(9900,'精选测试0','测试屏蔽','manual',?,NULL)").run(now());
assert.equal((await call('owner','adminFeatured',undefined,{}, {q:'精选测试',state:'excluded'})).total,1);
assert.equal((await call('owner','adminFeature',{article:'9900',remove:true})).status,200);
assert.equal((await call('owner','adminFeature',{article:'9900'})).status,400);
assert.equal(sql.prepare('SELECT featured FROM articles WHERE id=9900').get()!.featured,-1);
// Only a vote-qualified entry is available, so the featured mode must select it.
sql.prepare('UPDATE articles SET featured=0 WHERE id<>9900').run();sql.prepare('UPDATE articles SET featured=2 WHERE id=9901').run();
assert.equal((await choose(db,'featured',[],null,false)).id,'9901');
// Removal must survive subsequent qualifying votes; re-adding remains explicit.
sql.prepare('UPDATE articles SET featured=-1 WHERE id=?').run(pageId);
for(let i=0;i<12;i++)sql.prepare('INSERT OR REPLACE INTO votes VALUES(?,?,1,?)').run('paging'+i,pageId,now());
await call('owner','adminUnblock',{pageId});
assert.equal((await call('alice','vote',{pageId,value:1})).status,200);
assert.equal(sql.prepare('SELECT featured FROM articles WHERE id=?').get(pageId)!.featured,-1);
assert.equal((await call('owner','adminFeature',{article:String(pageId)})).status,200);
assert.equal(sql.prepare('SELECT featured FROM articles WHERE id=?').get(pageId)!.featured,1);
assert(sql.prepare("SELECT COUNT(*) n FROM audit WHERE action='adminFeature'").get()!.n as number >=5);
console.log('PASS: featured admin permissions; search/category/status/source filters; pagination; detail; idempotent add; blocked removal; manual opt-out; automatic featured playable; audited changes.');
