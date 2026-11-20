import {one,now} from './core';
// Provisioned exclusively from server-side deployment secrets. No HTTP request
// can choose the account, credentials or role. Registration always creates users.
export async function ensureSuperAdmin(db:any,env:any){
 const id=env.SUPER_ADMIN_ID,username=env.SUPER_ADMIN_USERNAME,salt=env.SUPER_ADMIN_SALT,passwordHash=env.SUPER_ADMIN_HASH;
 if(!id||!username||!salt||!passwordHash)return;
 const marker=await one(db,"SELECT value FROM settings WHERE key='super_bootstrap'");if(marker?.value===id)return;
 const collision=await one(db,'SELECT id FROM users WHERE username=? AND id<>?',username,id);if(collision)throw new Error('Reserved administrator username is already in use');
 await db.batch([
 db.prepare("INSERT INTO users(id,username,password_hash,salt,nickname,role,created_at) VALUES(?,?,?,?,'超级管理员','super',?) ON CONFLICT(id) DO UPDATE SET role='super'").bind(id,username,passwordHash,salt,now()),
 db.prepare("UPDATE users SET role='user' WHERE role='super' AND id<>?").bind(id),
 db.prepare("INSERT INTO settings VALUES('super_user',?) ON CONFLICT(key) DO UPDATE SET value=excluded.value").bind(id),
 db.prepare("INSERT INTO settings VALUES('super_bootstrap',?) ON CONFLICT(key) DO UPDATE SET value=excluded.value").bind(id)
 ]);
}
