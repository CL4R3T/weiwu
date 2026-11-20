'use client';
import React,{useEffect,useRef,useState} from 'react';
import {TOPIC_GROUPS,topicById,topicLabel} from '../../lib/topics';

type RequestAPI=(action:string,data?:any,query?:Record<string,string>)=>Promise<any>;
export function FeaturedManager({request}:{request:RequestAPI}){
 const [query,setQuery]=useState(''),[search,setSearch]=useState(''),[kind,setKind]=useState(''),[state,setState]=useState(''),[filter,setFilter]=useState(''),[page,setPage]=useState(0),[revision,setRevision]=useState(0);
 const [data,setData]=useState<any>(null),[busy,setBusy]=useState(true),[error,setError]=useState(''),[notice,setNotice]=useState(''),[input,setInput]=useState(''),[detail,setDetail]=useState<any>(null),[removing,setRemoving]=useState<number|null>(null);
 const generation=useRef(0);
 const selected=topicById(filter),group=TOPIC_GROUPS.find(g=>g.id===(selected?.group||filter));
 useEffect(()=>{const token=++generation.current;setBusy(true);setError('');setDetail(null);setRemoving(null);
 request('adminFeatured',undefined,{q:search,kind,state,filter,offset:String(page*20)}).then(d=>{
  if(token!==generation.current)return;
  if(page>0&&!d.articles.length){setPage(Math.max(0,Math.ceil(d.total/20)-1));return;}
  setData(d);
 }).catch(e=>{if(token===generation.current){setError(e.message);setData(null)}}).finally(()=>{if(token===generation.current)setBusy(false)});
 return()=>{generation.current++};
 },[request,search,kind,state,filter,page,revision]);
 async function change(article:string,remove=false){if(busy)return;setBusy(true);setError('');setNotice('');try{const result=await request('adminFeature',{article,remove});setNotice(result.title+(remove?'已移出精选':'已加入精选'));if(!remove)setInput('');setRevision(v=>v+1)}catch(e){setError((e as Error).message)}finally{setBusy(false)}}
 async function preview(id:number){if(busy)return;if(detail?.id===id){setDetail(null);return;}setBusy(true);setError('');try{setDetail(await request('adminArticleDetail',undefined,{id:String(id)}))}catch(e){setError((e as Error).message)}finally{setBusy(false)}}
 const reset=()=>{setPage(0);setDetail(null);setRemoving(null)};
 return <div className="featured-manager" aria-busy={busy}>
  <section className="card sectionpad"><h2>新增精选</h2>
   <form className="inlineform" onSubmit={e=>{e.preventDefault();change(input.trim())}}><input aria-label="精选词条名称或 pageid" value={input} maxLength={255} onChange={e=>setInput(e.target.value)} placeholder="中文维基词条名称或 pageid" required/><button className="primary" disabled={busy||!input.trim()}>加入精选</button></form>
  </section>
  {error&&<p className="message error" role="alert">{error}</p>}{notice&&<p className="message" role="status">{notice}</p>}
  <section className="card sectionpad">
   <div className="featured-heading"><h2>精选词条{data?' · '+data.total:''}</h2><button className="secondary" disabled={busy} onClick={()=>setRevision(v=>v+1)}>刷新列表</button></div>
   <div className="tabs">{[['','全部精选'],['manual','人工精选'],['auto','自动精选'],['removed','移除记录']].map(([value,label])=><button key={value} className={kind===value?'selected':''} aria-pressed={kind===value} disabled={busy} onClick={()=>{setKind(value);reset()}}>{label}</button>)}</div>
   <form className="inlineform" onSubmit={e=>{e.preventDefault();setSearch(query.trim());reset();setRevision(v=>v+1)}}><input aria-label="搜索精选词条" placeholder="搜索词条名称或 pageid" maxLength={80} value={query} onChange={e=>setQuery(e.target.value)}/><button className="secondary" disabled={busy}>搜索</button></form>
   <div className="topic-select"><label>一级分类<select disabled={busy} value={group?.id||''} onChange={e=>{setFilter(e.target.value);reset()}}><option value="">全部大类</option>{TOPIC_GROUPS.map(g=><option key={g.id} value={g.id}>{g.name}</option>)}</select></label>
    <label>二级分类<select disabled={busy||!group} value={selected?.id||''} onChange={e=>{setFilter(e.target.value||group?.id||'');reset()}}><option value="">全部小类</option>{group?.children.map(t=><option key={t.id} value={t.id}>{t.name}</option>)}</select></label>
    <label>可用状态<select disabled={busy} value={state} onChange={e=>{setState(e.target.value);reset()}}><option value="">全部状态</option><option value="active">可用</option><option value="excluded">已屏蔽</option></select></label>
   </div>
   <div className="tablewrap"><table><thead><tr><th>词条 / ID</th><th>分类</th><th>赞 / 踩</th><th>入选方式 / 状态</th><th>操作</th></tr></thead><tbody>{data?.articles.map((a:any)=><React.Fragment key={a.id}><tr>
    <td><a href={'https://zh.wikipedia.org/?curid='+a.id} target="_blank" rel="noreferrer">{a.title}</a><small>{a.id}</small></td>
    <td>{a.topics?a.topics.split(',').map((id:string)=><small key={id}>{topicLabel(id)}</small>):'待归类'}</td>
    <td>{a.likes} / {a.dislikes}<small>好评率 {a.likes+a.dislikes?Math.round(a.likes/(a.likes+a.dislikes)*100)+'%':'—'}</small></td>
    <td>{a.featured===1?'人工精选':a.featured===2?'自动精选':'已移除'}<small>{a.status==='active'?'可用':'已屏蔽'}{a.reason?' · '+a.reason:''}</small></td>
    <td><div className="featured-actions"><button className="textbtn" disabled={busy} aria-expanded={detail?.id===a.id} onClick={()=>preview(a.id)}>{detail?.id===a.id?'收起预览':'查看目录'}</button>
     {a.featured===2&&<button className="textbtn" disabled={busy||a.status!=='active'} onClick={()=>change(String(a.id))}>转为人工精选</button>}
     {a.featured>0?<button className="textbtn" disabled={busy} onClick={()=>setRemoving(a.id)}>移出精选</button>:<button className="textbtn" disabled={busy||a.status!=='active'} onClick={()=>change(String(a.id))}>重新加入</button>}</div>
     {removing===a.id&&<div className="featured-confirm"><p>移出精选？此后不会自动入选，也不会屏蔽该词条。</p><button className="danger-btn" disabled={busy} onClick={()=>change(String(a.id),true)}>确认移出</button><button className="secondary" disabled={busy} onClick={()=>setRemoving(null)}>取消</button></div>}
    </td></tr>{detail?.id===a.id&&<tr><td colSpan={5}><div className="featured-preview"><h3>{detail.title}</h3>{detail.summary&&<p>{detail.summary}</p>}<ol>{detail.sections.map((s:any,i:number)=><li key={i} style={{paddingLeft:Math.min(6,Math.max(0,s.level-1))*16}}><span>{s.number}</span> {s.text}</li>)}</ol>{!detail.sections.length&&<p>暂无目录。</p>}</div></td></tr>}</React.Fragment>)}</tbody></table></div>
   {!data?.articles.length&&<p className="empty">{busy?'正在加载…':'暂无匹配词条。'}</p>}
   {data&&<div className="pagination"><button disabled={busy||page===0} onClick={()=>setPage(v=>v-1)}>上一页</button><span>第 {page+1} / {Math.max(1,Math.ceil(data.total/20))} 页 · 共 {data.total} 条</span><button disabled={busy||!data.hasMore} onClick={()=>setPage(v=>v+1)}>下一页</button></div>}
  </section>
 </div>
}
