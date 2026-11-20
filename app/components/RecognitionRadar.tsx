'use client';
import React,{useId,useState} from 'react';
import type {RecognitionAxis} from '../../lib/recognition';
const labels=[['生活、艺术','与文化'],['世界各地'],['中华文化'],['人文与','社会科学'],['社会'],['自然与','自然科学'],['宗教及信仰'],['工程、技术','与应用科学']];
export function RecognitionRadar({rows}:{rows:RecognitionAxis[]}){
 const id=useId();const [selected,setSelected]=useState<string|null>(null);const focus=rows.find(r=>r.id===selected);const complete=rows.length===8&&rows.every(r=>r.score!==null),hasData=rows.some(r=>r.total>0);
 const point=(index:number,value:number)=>{const a=index*Math.PI/4-Math.PI/2;return [240+Math.cos(a)*142*value/100,220+Math.sin(a)*142*value/100]};
 const polygon=(value:number)=>rows.map((_,i)=>point(i,value).join(',')).join(' ');
 return <div className="recognition"><div className="radar-layout"><div className="radar-figure"><svg viewBox="0 0 480 440" role="img" aria-labelledby={id+'-title '+id+'-desc'}><title id={id+'-title'}>八大类目录识别率雷达图</title><desc id={id+'-desc'}>各轴范围为0至100%。未作答分类按0分绘制，有样本的分类按实际识别率绘制。具体数据见旁边分类按钮。</desc>
 {[25,50,75,100].map(n=><g key={n}><polygon points={polygon(n)} fill="none" stroke="#dce3d4"/><text x={246} y={220-142*n/100+4} className="radar-scale">{n}</text></g>)}
 {rows.map((r,i)=>{const [x,y]=point(i,100),[tx,ty]=point(i,127);return <g key={r.id}><line x1="240" y1="220" x2={x} y2={y} stroke="#dce3d4"/><text x={tx} y={ty-(labels[i].length-1)*7} textAnchor="middle" className="radar-label">{labels[i].map((line,j)=><tspan key={j} x={tx} dy={j?15:0}>{line}</tspan>)}</text></g>})}
 {complete&&<polygon points={rows.map((r,i)=>point(i,r.score!).join(',')).join(' ')} fill="#b9cf7980" stroke="#4b6738" strokeWidth="2"/>}
 {!complete&&rows.map((r,i)=>{const next=rows[(i+1)%8];if(r.score===null||next?.score===null||!next)return null;const [x1,y1]=point(i,r.score),[x2,y2]=point((i+1)%8,next.score!);return <line key={r.id} x1={x1} y1={y1} x2={x2} y2={y2} stroke="#4b6738" strokeWidth="2"/>})}
 {rows.map((r,i)=>{if(r.score===null)return null;const [cx,cy]=point(i,r.score);return <circle key={r.id} cx={cx} cy={cy} r={selected===r.id?6:4} fill={r.smallSample?'#fffef9':'#4b6738'} stroke="#4b6738" strokeWidth="2"><title>{`${r.category}：${r.score}%，${r.won}/${r.total}题`}</title></circle>})}
 {!hasData&&<text x="240" y="235" textAnchor="middle" className="radar-label">暂无已归类答题记录</text>}
 </svg></div><div className="radar-values" aria-label="各分类识别率">{rows.map(r=><button type="button" key={r.id} className={selected===r.id?'selected':''} aria-pressed={selected===r.id} onClick={()=>setSelected(selected===r.id?null:r.id)}><span>{r.category}<small>{r.total?`${r.won} / ${r.total} 题${r.smallSample?' · 样本较少':''}`:'未作答'}</small></span><b>{(r.score??0)+'%'}</b></button>)}</div></div>
 {focus&&<p className="radar-detail" role="status">{focus.category}：{focus.total?`首次完成 ${focus.total} 个词条，答对 ${focus.won} 个，识别率 ${focus.score}%。`:'尚无已完成词条，按0分显示。'}</p>}
 <details className="radar-rules"><summary>计算标准</summary><p>识别率 = 首次答对词条数 ÷ 首次完成词条数 × 100%。</p><ul><li>每个词条只采用首次完成的结果；揭晓答案或用尽次数计未答对，进行中的题不计。</li><li>待归类词条不参与计算。一个词条属于多个大类时，在各大类各计一次，同一大类内不重复。</li><li>只有未作答的分类按0分显示；有样本即按实际识别率计算。样本较少标注和空心点不影响分数。</li><li>所有玩法均计入，不按用时或猜测次数加权。结果反映已玩题目的目录识别表现，受选题范围与提示影响。</li></ul></details></div>
}
