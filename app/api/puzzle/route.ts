// The legacy endpoint exposed answer IDs without an authenticated attempt.
export const GET=()=>Response.json({error:'请刷新页面，使用新版维雾主义。'},{status:410});
export const POST=GET;
