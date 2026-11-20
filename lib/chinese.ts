import {Converter} from 'opencc-js/t2cn';

// One shared converter per server process. Keep original Wiki identifiers intact.
const convert = Converter({from:'t', to:'cn'});
export const simplified = (text:string) => convert(text);

/** Convert Wiki display fields only, never account data, guesses, IDs or URLs. */
export function simplifiedDisplay(value:any, field=''):any {
 if(typeof value==='string')return ['title','summary','category','groupName','hints'].includes(field)?simplified(value):value;
 if(Array.isArray(value))return value.map(item=>simplifiedDisplay(item,field));
 if(!value||typeof value!=='object')return value;
 return Object.fromEntries(Object.entries(value).map(([key,item])=>[
  key,field==='sections'&&key==='text'&&typeof item==='string'?simplified(item):simplifiedDisplay(item,key)
 ]));
}
