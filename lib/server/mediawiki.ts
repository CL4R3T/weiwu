const UA={'User-Agent':'Weiwu/2.0 (Wikipedia TOC game; https://wiki-mystery-tfh.achromakui.chatgpt.site)'};
export async function wiki(p:Record<string,string>){const r=await fetch('https://zh.wikipedia.org/w/api.php?'+new URLSearchParams({format:'json',...p}),{headers:UA,signal:AbortSignal.timeout(10000)});if(!r.ok)throw new Error('维基连接暂不可用（'+r.status+'），请稍后重试。');const j:any=await r.json();if(j.error){const e:any=new Error('维基返回：'+j.error.code);e.code=j.error.code;throw e;}return j;}
export async function officialAnswer(answer:string,pageId:number):Promise<'correct'|'wrong'|'ambiguous'>{
 let j:any;try{j=await wiki({action:'query',titles:answer,redirects:'1',converttitles:'1',prop:'pageprops',ppprop:'disambiguation'});}catch(e:any){if(['invalidtitle','badtitle'].includes(e.code))return 'wrong';throw e;}
 const pages:any[]=Object.values(j.query?.pages||{});const valid=pages.filter(p=>p.ns===0&&p.missing===undefined&&p.invalid===undefined&&Number(p.pageid)>0);
 if(valid.some(p=>Number(p.pageid)===pageId))return 'correct';
 return valid.some(p=>Object.prototype.hasOwnProperty.call(p.pageprops||{},'disambiguation'))?'ambiguous':'wrong';
}
