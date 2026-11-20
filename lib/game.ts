import {simplified} from './chinese';
export type Section={text:string;level:number;number:string};
export type Article={id:string;title:string;canonical:string;aliases:string[];category:string;topics?:{name:string}[];sections:Section[];revision?:number;traditional?:string;fetchedAt:string};
export function normalize(s:string){return simplified(s).normalize('NFKC').toLowerCase().replace(/[\s\p{P}\p{S}]/gu,'')}
export function maskSections(a:Article){
 const chars=new Set(Array.from(simplified(a.title+a.canonical+(a.traditional||'')).toLowerCase()).filter(c=>/[\p{L}\p{N}]/u.test(c)));
 return a.sections.map(s=>({...s,text:Array.from(simplified(s.text)).map(c=>chars.has(c.toLowerCase())?'■':c).join('')}));
}
export function beijingDate(now=new Date()){return new Intl.DateTimeFormat('en-CA',{timeZone:'Asia/Shanghai',year:'numeric',month:'2-digit',day:'2-digit'}).format(now)}
export function dateIndex(date:string,count:number){const day=Math.floor(Date.parse(date+'T00:00:00+08:00')/86400000);return ((day+11)%count+count)%count}
export function baseTitle(t:string){return t.replace(/\s*[（(][^()（）]*[）)]\s*$/u,'').trim()}
export function match(a:Article,guess:string){const g=normalize(guess);return !!g&&a.aliases.concat(a.title,a.canonical).some(t=>normalize(t)===g||normalize(baseTitle(t))===g)}
export function hints(a:Article,wrong:number,topic=false){const title=baseTitle(simplified(a.title));const values=[`二级分类：${[...new Set((a.topics||[]).map(t=>t.name))].join('、')||'待归类'}`,`字数：${Array.from(title).length}`,`第一个字：${Array.from(title)[0]||''}`];return (topic?values.slice(1):values).slice(0,Math.max(0,wrong));}
export function clean(s:string){return s.replace(/<[^>]*>/g,'').replace(/&amp;/g,'&').replace(/&quot;/g,'"').replace(/&#39;/g,"'").replace(/&lt;/g,'<').replace(/&gt;/g,'>').replace(/&#(\d+);/g,(_,x)=>String.fromCodePoint(Number(x))).trim()}
