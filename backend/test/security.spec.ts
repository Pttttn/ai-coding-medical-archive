import {isAllowedRequest,weakPersonalSecrets} from '../src/security';

const strong={ARCHIVE_MODE:'personal',DATABASE_URL:'postgresql://archive:synthetic-strong-password-1@postgres:5432/archive',INTERNAL_API_TOKEN:'synthetic-strong-token-0001'};
describe('Loopback request guard',()=>{
  it('accepts loopback hosts with and without ports',()=>{for(const host of ['localhost','127.0.0.1:3000','[::1]:8080','LocalHost:8080'])expect(isAllowedRequest(host,undefined)).toBe(true);});
  it('accepts same-device browser origins',()=>{expect(isAllowedRequest('127.0.0.1:8080','http://127.0.0.1:8080')).toBe(true);expect(isAllowedRequest('localhost:5173','http://localhost:5173')).toBe(true);});
  it('rejects DNS-rebinding hosts',()=>{for(const host of ['attacker.example:3000','localhost.attacker.example','127.0.0.1.nip.io:3000',undefined,''])expect(isAllowedRequest(host,undefined)).toBe(false);});
  it('rejects cross-site and opaque origins',()=>{for(const origin of ['http://attacker.example','https://localhost:8080','null','http://localhost.attacker.example'])expect(isAllowedRequest('127.0.0.1:3000',origin)).toBe(false);});
});
describe('Personal mode secrets',()=>{
  it('keeps demo defaults for the synthetic demo',()=>{expect(weakPersonalSecrets({DATABASE_URL:'postgresql://archive:local-demo-password@postgres:5432/archive',INTERNAL_API_TOKEN:'local-internal-demo-token'})).toEqual([]);});
  it('refuses demo defaults in personal mode',()=>{expect(weakPersonalSecrets({...strong,DATABASE_URL:'postgresql://archive:local-demo-password@postgres:5432/archive',INTERNAL_API_TOKEN:'local-internal-demo-token'})).toEqual(['POSTGRES_PASSWORD','INTERNAL_API_TOKEN']);});
  it('refuses missing and short secrets',()=>{expect(weakPersonalSecrets({ARCHIVE_MODE:'personal'})).toEqual(['POSTGRES_PASSWORD','INTERNAL_API_TOKEN']);expect(weakPersonalSecrets({...strong,INTERNAL_API_TOKEN:'short'})).toEqual(['INTERNAL_API_TOKEN']);});
  it('accepts strong URL-encoded secrets',()=>{expect(weakPersonalSecrets(strong)).toEqual([]);expect(weakPersonalSecrets({...strong,DATABASE_URL:'postgresql://archive:synthetic%40strong%2Fpass@postgres:5432/archive'})).toEqual([]);});
});
