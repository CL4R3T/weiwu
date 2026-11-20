import {one} from './core';

// Use the exact same population for the public count and random selection.
export const FEATURED_WHERE="a.featured IN (1,2) AND a.status IN ('active','pending_views') AND NOT EXISTS(SELECT 1 FROM exclusions e WHERE e.page_id=a.id)";
export async function featuredCount(db:any):Promise<number>{
 return Number((await one(db,'SELECT COUNT(*) count FROM articles a WHERE '+FEATURED_WHERE))?.count||0);
}
