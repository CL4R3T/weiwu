import {TOPIC_GROUPS} from './topics';
export type RecognitionAxis={id:string;category:string;total:number;won:number;score:number;smallSample:boolean};
// Rate of successful first completed encounters, not an estimate of general knowledge.
// Unknown categories never supply an axis or a denominator.
export function recognitionAxes(rows:{category:string;total:number;won:number}[]):RecognitionAxis[]{
 return TOPIC_GROUPS.map(g=>{const row=rows.find(r=>r.category===g.id);const total=Number(row?.total||0),won=Number(row?.won||0);return {id:g.id,category:g.name,total,won,score:total>0?Math.round(1000*won/total)/10:0,smallSample:total>0&&total<5};});
}
