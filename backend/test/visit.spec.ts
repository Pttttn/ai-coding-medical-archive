import {readFileSync} from 'node:fs';
import {join} from 'node:path';
import {irHash} from '../src/source-ir';
import {validateVisit} from '../src/visit';
const fixture=()=>JSON.parse(readFileSync(join(__dirname,'../../contracts/visit-assertions-v1.synthetic.json'),'utf8'));

test('accepts Python VISIT artifact with conservative legacy projection',()=>{
  const f=fixture();expect(()=>validateVisit(f.visit,f.sourceIR,f.extraction)).not.toThrow();
  expect(f.extraction.facts[1]).toMatchObject({type:'OBSERVATION',assertionStatus:'UNKNOWN'});
  expect(f.extraction.facts[5].assertionStatus).toBe('UNKNOWN');
});
test.each(['source','context','revision','family-promotion','medication-promotion','state','date','duplicate','block','name'])('rejects %s across service boundary',kind=>{
  const f=fixture(),v=f.visit;
  if(kind==='source')v.statements[0].source.startByte++;
  if(kind==='context')v.statements[0].contextText='Narrowed fabricated context';
  if(kind==='revision')v.sourceIRHash='other';
  if(kind==='family-promotion')f.extraction.facts[1].assertionStatus='CONFIRMED';
  if(kind==='medication-promotion')f.extraction.facts[5].assertionStatus='CONFIRMED';
  if(kind==='state')v.statements[0].medicationState='TAKING';
  if(kind==='date')f.extraction.documentDate='2026-09-25';
  if(kind==='duplicate'){v.statements.push(v.statements[0]);f.extraction.facts.push(f.extraction.facts[0]);}
  if(kind==='block')v.processedBlocks=[];
  if(kind==='name')v.statements[0].name='Not present';
  const {artifactHash,...body}=v;void artifactHash;v.artifactHash=irHash(body);
  expect(()=>validateVisit(v,f.sourceIR,f.extraction)).toThrow();
});
