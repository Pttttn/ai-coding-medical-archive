import {readFileSync} from 'node:fs';
import {join} from 'node:path';
import {irHash} from '../src/source-ir';
import {validateLaboratory} from '../src/laboratory';
const fixture=()=>JSON.parse(readFileSync(join(__dirname,'../../contracts/lab-rows-v1.synthetic.json'),'utf8'));
test('accepts Python lab artifact and exact fact projection',()=>{
  const f=fixture();expect(()=>validateLaboratory(f.laboratory,f.sourceIR,f.facts)).not.toThrow();
});
test.each(['numeric','comparator','source','version','duplicate','date','subject','unit'])('rejects inconsistent %s with recomputed hash',kind=>{
  const f=fixture(),lab=f.laboratory;
  if(kind==='numeric')lab.rows[1].result.numericValue='174.20';
  if(kind==='comparator')f.facts[0].valueNumber=5;
  if(kind==='source')lab.rows[0].source.startByte++;
  if(kind==='version')lab.sourceIRHash='another-revision';
  if(kind==='duplicate')lab.rows[1].source=lab.rows[0].source;
  if(kind==='date')f.facts[0].eventDate='2026-06-17';
  if(kind==='subject')lab.subjectSources=[];
  if(kind==='unit')f.facts[1].unit='mg';
  const {artifactHash,...body}=lab;void artifactHash;lab.artifactHash=irHash(body);
  expect(()=>validateLaboratory(lab,f.sourceIR,f.facts)).toThrow();
});
