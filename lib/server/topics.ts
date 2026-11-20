import {TOPICS,categoryKey,directTopics,topicById,topicCategory,type TopicMatch} from '../topics';
import {all,one,run,now,err} from './core';
import {wiki} from './mediawiki';
const category=(s:string)=>'Category:'+categoryKey(s);
export async function saveTopics(db:any,a:any,topics:TopicMatch[]){
 const merged=new Map<string,TopicMatch>((a.topics||[]).map((t:TopicMatch)=>[t.id,t]));for(const t of topics){const old=merged.get(t.id);if(!old||old.path.length>t.path.length)merged.set(t.id,t);}
 a.topics=[...merged.values()].sort((x,y)=>x.path.length-y.path.length||x.id.localeCompare(y.id));a.category=topicCategory(a.topics);a.taxonomyVersion=1;a.classifiedAt=now();
 const statements=a.topics.map((t:TopicMatch)=>db.prepare('INSERT INTO article_topics VALUES(?,?,?,?,?) ON CONFLICT(page_id,topic) DO UPDATE SET path=excluded.path,distance=excluded.distance').bind(Number(a.id),t.id,t.group,JSON.stringify(t.path),t.path.length));
 statements.push(db.prepare('UPDATE articles SET category=?,data=? WHERE id=?').bind(a.category,JSON.stringify(a),Number(a.id)));for(let i=0;i<statements.length;i+=40)await db.batch(statements.slice(i,i+40));return a;
}
// Breadth-first traversal follows actual category links, with a visited set and bounded work.
// Unresolved articles remain explicitly unclassified; later visits reuse cached graph edges.
export async function classifyArticle(db:any,a:any){
 if(a.taxonomyVersion===1&&a.topics?.length)return a;
 const existing=await all(db,'SELECT * FROM article_topics WHERE page_id=?',Number(a.id));if(existing.length)return saveTopics(db,a,existing.flatMap((r:any)=>{const t=topicById(r.topic);return t?[{id:t.id,name:t.name,group:t.group,groupName:t.groupName,path:JSON.parse(r.path)}]:[]}));
 let frontier=(a.categories||[]).map((s:string)=>({name:category(s),path:[category(s)]}));let visited=new Set<string>();const found:TopicMatch[]=[];let calls=0;const deadline=now()+12000;
 for(let depth=0;depth<7&&frontier.length&&now()<deadline;depth++){
  const nodes:any[]=frontier.filter((n:any)=>!visited.has(categoryKey(n.name))).slice(0,80);frontier=[];
  for(const n of nodes){visited.add(categoryKey(n.name));for(const t of directTopics([n.name]))found.push({...t,path:n.path});}
  // Finish all matches at the nearest graph distance; avoid unrelated very broad ancestors.
  if(found.length)break;
  const cached=new Map<string,string[]>();const missing:string[]=[];
  for(const n of nodes){const row=await one(db,'SELECT parents FROM category_nodes WHERE name=? AND updated>?',n.name,now()-30*86400000);if(row)cached.set(n.name,JSON.parse(row.parents));else missing.push(n.name);}
  for(let offset=0;offset<missing.length&&calls<4&&now()<deadline;offset+=40){const names=missing.slice(offset,offset+40);let cursor:any=null;const parents=new Map<string,Set<string>>();const aliases=new Map<string,string>();let complete=false;
   do{const j=await wiki({action:'query',titles:names.join('|'),redirects:'1',converttitles:'1',prop:'categories|categoryinfo',clshow:'!hidden',cllimit:'500',...cursor});calls++;
    for(const edge of [...(j.query?.normalized||[]),...(j.query?.converted||[]),...(j.query?.redirects||[])])aliases.set(edge.from,edge.to);
    for(const p of Object.values(j.query?.pages||{}) as any[]){if(!p.title)continue;const values=parents.get(p.title)||new Set<string>();if(!p.categoryinfo?.hidden)for(const c of p.categories||[])values.add(c.title);parents.set(p.title,values);}
    cursor=j.continue;complete=!cursor;
   }while(cursor&&calls<4&&now()<deadline);
   for(const name of names){let canonical=name;const seen=new Set<string>();while(aliases.has(canonical)&&!seen.has(canonical)){seen.add(canonical);canonical=aliases.get(canonical)!;}const values=[...(parents.get(canonical)||[])];if(canonical!==name)values.unshift(canonical);cached.set(name,values);if(complete)await run(db,'INSERT INTO category_nodes VALUES(?,?,?) ON CONFLICT(name) DO UPDATE SET parents=excluded.parents,updated=excluded.updated',name,JSON.stringify(values),now());}
  }
  for(const n of nodes)for(const parent of cached.get(n.name)||[])if(!visited.has(categoryKey(parent)))frontier.push({name:category(parent),path:[...n.path,category(parent)]});
 }
 return saveTopics(db,a,found);
}
export async function enrichArticle(db:any,a:any){try{return await classifyArticle(db,a);}catch(e){console.error('Category lookup',String(e));return saveTopics(db,{...a,topics:a.topics||[]},a.topics||[]);}}
export async function refreshTopic(db:any,source:string){
 const t=topicById(source);if(!t)err('无效专题');await run(db,'INSERT OR IGNORE INTO topic_queue VALUES(?,?,?,NULL,0,0)',source,t!.category,JSON.stringify([t!.category]));
 const job=await one(db,'SELECT * FROM topic_queue WHERE source=? AND done=0 ORDER BY updated,category LIMIT 1',source);if(!job)return {complete:true,added:0};
 const j=await wiki({action:'query',list:'categorymembers',cmtitle:job.category,cmtype:'page|subcat',cmlimit:'100',...(job.cursor?JSON.parse(job.cursor):{})});const path=JSON.parse(job.path),stmts=[];
 for(const p of j.query?.categorymembers||[]){if(p.ns===0){stmts.push(db.prepare('INSERT OR IGNORE INTO topic_members VALUES(?,?,?,?)').bind(source,p.pageid,p.title,job.path));}else if(p.ns===14&&!path.includes(p.title)){stmts.push(db.prepare('INSERT OR IGNORE INTO topic_queue VALUES(?,?,?,NULL,0,0)').bind(source,p.title,JSON.stringify([...path,p.title])));}}
 stmts.push(db.prepare('UPDATE topic_queue SET cursor=?,done=?,updated=? WHERE source=? AND category=?').bind(j.continue?JSON.stringify(j.continue):null,j.continue?0:1,now(),source,job.category));for(let i=0;i<stmts.length;i+=40)await db.batch(stmts.slice(i,i+40));return {complete:!await one(db,'SELECT category FROM topic_queue WHERE source=? AND done=0',source),added:(j.query?.categorymembers||[]).filter((p:any)=>p.ns===0).length};
}
export async function topicCandidates(db:any,source:string,userId:string|null,skip:boolean){
 if(process.env.WIKI_SNAPSHOT_ONLY==='true'){
  const candidates=await all(db,"SELECT a.id,t.path FROM article_topics t JOIN articles a ON a.id=t.page_id WHERE t.topic=? AND a.status IN ('active','pending_views') AND NOT EXISTS(SELECT 1 FROM exclusions e WHERE e.page_id=a.id)"+(skip&&userId?" AND NOT EXISTS(SELECT 1 FROM games g WHERE g.page_id=a.id AND g.user_id=? AND g.state<>'playing')":"")+' ORDER BY RANDOM() LIMIT 24',source,...(skip&&userId?[userId]:[]));
  if(!candidates.length)err('当前专题暂无可用新题，请选择其他专题。',503);
  return candidates;
 }
 // Expand one official category batch on every draw so selection is not frozen to root pages.
 await refreshTopic(db,source);
 const candidates=await all(db,"SELECT m.page_id id,m.path FROM topic_members m WHERE source=? AND NOT EXISTS(SELECT 1 FROM exclusions e WHERE e.page_id=m.page_id) AND NOT EXISTS(SELECT 1 FROM selection_skips s WHERE (s.title=CAST(m.page_id AS TEXT) OR s.title=m.title) AND s.retry_after>?)"+(skip&&userId?" AND NOT EXISTS(SELECT 1 FROM games g WHERE g.page_id=m.page_id AND g.user_id=? AND g.state<>'playing')":'')+' ORDER BY RANDOM() LIMIT 12',source,now(),...(skip&&userId?[userId]:[]));
 if(!candidates.length&&!await one(db,'SELECT category FROM topic_queue WHERE source=? AND done=0',source))err('当前专题暂无可用新题，请选择其他专题。',503);return candidates;
}
