import {handle} from '../../../lib/server/service';
import {database} from '../../../lib/server/postgres';
export const dynamic='force-dynamic';
export const runtime='nodejs';
export const GET=(req:Request)=>handle(req,database,process.env);
export const POST=(req:Request)=>handle(req,database,process.env);
