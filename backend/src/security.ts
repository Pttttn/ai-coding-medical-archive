// The API has no authentication and is published on loopback only. These guards keep
// a DNS-rebinding or cross-site page from reading or changing the archive.
const LOOPBACK_HOST=/^(localhost|127\.0\.0\.1|\[::1\])(:\d{1,5})?$/i;
const LOOPBACK_ORIGIN=/^http:\/\/(localhost|127\.0\.0\.1|\[::1\])(:\d{1,5})?$/i;
export const DEMO_SECRETS=['local-demo-password','local-internal-demo-token'];
export const MIN_PERSONAL_SECRET_LENGTH=16;

export function isAllowedRequest(host:string|undefined,origin:string|undefined) {
  if(!host||!LOOPBACK_HOST.test(host))return false;
  return origin===undefined||LOOPBACK_ORIGIN.test(origin);
}

export function loopbackGuard(req:any,res:any,next:any) {
  if(isAllowedRequest(req.headers.host,req.headers.origin))return next();
  res.status(403).json({statusCode:403,code:'FORBIDDEN_ORIGIN',message:'Архив доступен только с этого устройства.'});
}

function weak(secret:string|undefined) {
  return !secret||secret.length<MIN_PERSONAL_SECRET_LENGTH||DEMO_SECRETS.includes(secret);
}

// Returns the names of weak settings; empty when the mode is not personal or all are strong.
export function weakPersonalSecrets(env:NodeJS.ProcessEnv=process.env) {
  if(env.ARCHIVE_MODE!=='personal')return [];
  let password:string|undefined;
  try{password=decodeURIComponent(new URL(env.DATABASE_URL??'').password)||undefined;}catch{password=undefined;}
  return [...(weak(password)?['POSTGRES_PASSWORD']:[]),...(weak(env.INTERNAL_API_TOKEN)?['INTERNAL_API_TOKEN']:[])];
}
