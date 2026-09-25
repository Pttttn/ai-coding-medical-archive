import {readFileSync} from 'node:fs';
import {join} from 'node:path';
import {irHash} from '../src/source-ir';
import {validateVisit} from '../src/visit';
const fixture=()=>JSON.parse(readFileSync(join(__dirname,'../../contracts/visit-assertions-v2.synthetic.json'),'utf8'));
test('accepts a disagreement while quarantining the first-pass taking claim',()=>{
  const f=fixture();expect(()=>validateVisit(f.visit,f.sourceIR,f.extraction)).not.toThrow();
  expect(f.visit.statements[5].medicationState).toBe('TAKING');
  expect(f.extraction.facts[5]).toMatchObject({type:'OBSERVATION',assertionStatus:'UNKNOWN'});
});
test.each(['promote','verdict','anchor','index','missing','null','version','other-target'])('rejects reviewed artifact %s',kind=>{
  const f=fixture(),v=f.visit;
  if(kind==='promote'){f.extraction.facts[5].type='MEDICATION';f.extraction.facts[5].assertionStatus='CONFIRMED';}
  if(kind==='verdict')v.verifications[5].status='AGREES';
  if(kind==='anchor')v.verifications[5].alternative.source.startByte++;
  if(kind==='index')v.verifications[5].statementIndex=0;
  if(kind==='missing')v.verifications.pop();
  if(kind==='null')v.verifications[0].alternative=null;
  if(kind==='version')v.reviewVersion='other';
  if(kind==='other-target')v.verifications[5].alternative=v.verifications[4].alternative;
  const {artifactHash,...body}=v;void artifactHash;v.artifactHash=irHash(body);
  expect(()=>validateVisit(v,f.sourceIR,f.extraction)).toThrow();
});
