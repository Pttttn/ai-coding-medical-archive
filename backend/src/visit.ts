import {TextDecoder} from 'node:util';
import {AiError} from './core';
import {irHash,SourceIR} from './source-ir';

type Span={pageIndex:number;startByte:number;endByte:number};
export type VisitStatement={blockId:string;name:string;kind:'CONDITION'|'SYMPTOM'|'MEDICATION';
  subject:'PATIENT'|'FAMILY'|'OTHER'|'UNKNOWN';assertion:'CONFIRMED'|'SUSPECTED'|'NEGATED'|'NOT_CONFIRMED'|'RULED_OUT'|'UNKNOWN';
  medicationState:'NOT_APPLICABLE'|'PRESCRIBED'|'TAKING'|'NOT_STARTED'|'NOT_TAKING'|'STOPPED'|'UNKNOWN';
  temporality:'CURRENT'|'HISTORICAL'|'FUTURE'|'UNKNOWN';sourceText:string;source:Span;contextSource:Span;contextText:string};
export type Visit={schemaVersion:'visit-assertions-v1';sourceIRHash:string;sourceHash:string;artifactHash:string;
  coverage:'CONDITIONS_SYMPTOMS_MEDICATIONS_ONLY';candidateBlocks:number;processedBlocks:string[];
  statements:VisitStatement[];issues:{code:string;blockId:string|null}[]};

export function visitStatus(s:VisitStatement):string {
  if(s.subject!=='PATIENT'||s.temporality!=='CURRENT')return 'UNKNOWN';
  if(s.kind==='MEDICATION')return s.medicationState==='TAKING'?'CONFIRMED':s.medicationState==='PRESCRIBED'?'PRESCRIBED':'UNKNOWN';
  return ['CONFIRMED','SUSPECTED','NEGATED'].includes(s.assertion)?s.assertion:'UNKNOWN';
}

// This validates structure, evidence and projection, not the model's clinical interpretation.
export function validateVisit(visit:Visit,ir:SourceIR|undefined,extraction:any):void {
  const fail=()=>{throw new AiError('VISIT_ARTIFACT_INVALID');};
  try {
    if(!ir||visit.schemaVersion!=='visit-assertions-v1'||visit.sourceIRHash!==ir.irHash||visit.sourceHash!==ir.sourceHash||visit.coverage!=='CONDITIONS_SYMPTOMS_MEDICATIONS_ONLY')fail();
    const {artifactHash,...body}=visit;
    if(artifactHash!==irHash(body)||!Array.isArray(visit.statements)||visit.statements.length>200||extraction.facts.length!==visit.statements.length||extraction.documentType!=='VISIT'||extraction.documentDate!==null)fail();
    const blocks=ir!.blocks.filter(b=>b.kind==='paragraph'),ids=new Set(blocks.map(b=>b.blockId));
    if(visit.candidateBlocks!==blocks.length||!Array.isArray(visit.processedBlocks)||new Set(visit.processedBlocks).size!==visit.processedBlocks.length||visit.processedBlocks.some(id=>!ids.has(id))||!Array.isArray(visit.issues))fail();
    for(const issue of visit.issues)if(!['UNSUPPORTED_BLOCK','BLOCK_LIMIT','OUTPUT_LIMIT','REJECTED_CANDIDATE','DUPLICATE','STATEMENT_LIMIT'].includes(issue.code)||(issue.blockId!==null&&!ids.has(issue.blockId)))fail();
    const decoder=new TextDecoder('utf8',{fatal:true});
    const resolve=(span:Span)=>{
      if(!span||![span.pageIndex,span.startByte,span.endByte].every(Number.isSafeInteger)||span.pageIndex<0||span.pageIndex>=ir!.pages.length||span.startByte<0||span.endByte<=span.startByte)fail();
      const raw=Buffer.from(ir!.pages[span.pageIndex].text);
      if(span.endByte>raw.length)fail();
      return decoder.decode(raw.subarray(span.startByte,span.endByte));
    };
    const seen=new Set<string>();
    for(const [index,s] of visit.statements.entries()){
      const block=blocks.find(b=>b.blockId===s.blockId),f=extraction.facts[index];
      if(!block||!visit.processedBlocks.includes(s.blockId)||irHash(block.source)!==irHash(s.contextSource)||resolve(s.contextSource)!==s.contextText||resolve(s.source)!==s.sourceText||s.source.pageIndex!==s.contextSource.pageIndex||s.source.startByte<s.contextSource.startByte||s.source.endByte>s.contextSource.endByte)fail();
      if(typeof s.name!=='string'||!s.name||s.name.length>200||!s.sourceText.includes(s.name)||s.contextText.split(s.sourceText).length!==2)fail();
      if(!['CONDITION','SYMPTOM','MEDICATION'].includes(s.kind)||!['PATIENT','FAMILY','OTHER','UNKNOWN'].includes(s.subject)||!['CONFIRMED','SUSPECTED','NEGATED','NOT_CONFIRMED','RULED_OUT','UNKNOWN'].includes(s.assertion)||!['NOT_APPLICABLE','PRESCRIBED','TAKING','NOT_STARTED','NOT_TAKING','STOPPED','UNKNOWN'].includes(s.medicationState)||!['CURRENT','HISTORICAL','FUTURE','UNKNOWN'].includes(s.temporality))fail();
      if(s.kind==='MEDICATION'?(s.assertion!=='UNKNOWN'||s.medicationState==='NOT_APPLICABLE'):s.medicationState!=='NOT_APPLICABLE')fail();
      const key=JSON.stringify([s.blockId,s.name,s.sourceText,s.kind,s.subject,s.assertion,s.medicationState,s.temporality]);
      if(seen.has(key))fail();seen.add(key);
      if(f.type!==(s.subject==='PATIENT'?s.kind:'OBSERVATION')||f.name!==s.name||f.valueText!==s.contextText||f.valueNumber!==null||f.unit!==null||f.eventDate!==null||f.confidence!==null||f.assertionStatus!==visitStatus(s)||f.provenance?.sourceText!==s.contextText||f.provenance?.page!==ir!.pages[s.source.pageIndex].pageNumber)fail();
    }
  }catch{fail();}
}
