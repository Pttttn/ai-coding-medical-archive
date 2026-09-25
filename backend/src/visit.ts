import {TextDecoder} from 'node:util';
import {AiError} from './core';
import {irHash,SourceIR} from './source-ir';

type Span={pageIndex:number;startByte:number;endByte:number};
export type VisitStatement={blockId:string;name:string;kind:'CONDITION'|'SYMPTOM'|'MEDICATION';
  subject:'PATIENT'|'FAMILY'|'OTHER'|'UNKNOWN';assertion:'CONFIRMED'|'SUSPECTED'|'NEGATED'|'NOT_CONFIRMED'|'RULED_OUT'|'UNKNOWN';
  medicationState:'NOT_APPLICABLE'|'PRESCRIBED'|'TAKING'|'NOT_STARTED'|'NOT_TAKING'|'STOPPED'|'UNKNOWN';
  temporality:'CURRENT'|'HISTORICAL'|'FUTURE'|'UNKNOWN';sourceText:string;source:Span;contextSource:Span;contextText:string};
export type Visit={schemaVersion:'visit-assertions-v1'|'visit-assertions-v2';reviewVersion?:string;verifications?:VisitVerification[];sourceIRHash:string;sourceHash:string;artifactHash:string;
  coverage:'CONDITIONS_SYMPTOMS_MEDICATIONS_ONLY';candidateBlocks:number;processedBlocks:string[];
  statements:VisitStatement[];issues:{code:string;blockId:string|null}[]};

export function visitStatus(s:VisitStatement):string {
  if(s.subject!=='PATIENT'||s.temporality!=='CURRENT')return 'UNKNOWN';
  if(s.kind==='MEDICATION')return s.medicationState==='TAKING'?'CONFIRMED':s.medicationState==='PRESCRIBED'?'PRESCRIBED':'UNKNOWN';
  return ['CONFIRMED','SUSPECTED','NEGATED'].includes(s.assertion)?s.assertion:'UNKNOWN';
}

// This validates structure, evidence and projection, not the model's clinical interpretation.
function validateVisitBase(visit:Visit,ir:SourceIR|undefined,extraction:any):void {
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

export type VisitVerification={statementIndex:number;status:'AGREES'|'DISAGREES'|'UNRESOLVED';reason:string;alternative:VisitStatement|null};
const semantics=['kind','subject','assertion','medicationState','temporality'] as const;
function withHash(body:any):any {const {artifactHash,...rest}=body;void artifactHash;return {...rest,artifactHash:irHash(rest)};}
function projection(s:VisitStatement,ir:SourceIR):any {
  return {type:s.subject==='PATIENT'?s.kind:'OBSERVATION',name:s.name,valueText:s.contextText,valueNumber:null,unit:null,eventDate:null,
    assertionStatus:visitStatus(s),confidence:null,provenance:{page:ir.pages[s.source.pageIndex].pageNumber,sourceText:s.contextText}};
}
export function validateVisit(visit:Visit,ir:SourceIR|undefined,extraction:any):void {
  const fail=()=>{throw new AiError('VISIT_ARTIFACT_INVALID');};
  try {
    if(visit.schemaVersion==='visit-assertions-v1'){
      if(visit.reviewVersion!==undefined||visit.verifications!==undefined)fail();
      return validateVisitBase(visit,ir,extraction);
    }
    if(!ir||visit.schemaVersion!=='visit-assertions-v2'||visit.reviewVersion!=='visit-review-v1'||!Array.isArray(visit.verifications)||visit.verifications.length!==visit.statements.length)fail();
    const {artifactHash,...body}=visit;
    if(artifactHash!==irHash(body))fail();
    const {reviewVersion,verifications,...original}=visit;void reviewVersion;
    const base=withHash({...original,schemaVersion:'visit-assertions-v1'});
    // Verify all original evidence, preserving actual values except the two quarantined projection fields.
    const restored={...extraction,facts:extraction.facts.map((f:any,i:number)=>({...f,type:visit.statements[i].subject==='PATIENT'?visit.statements[i].kind:'OBSERVATION',assertionStatus:visitStatus(visit.statements[i])}))};
    validateVisitBase(base,ir,restored);
    for(const [index,v] of verifications!.entries()){
      if(v.statementIndex!==index||!['AGREES','DISAGREES','UNRESOLVED'].includes(v.status))fail();
      const primary=visit.statements[index],alt=v.alternative;
      if(alt!==null){
        const altBase=withHash({...base,statements:[alt]});
        validateVisitBase(altBase,ir,{...extraction,facts:[projection(alt,ir!)]});
        if(alt.blockId!==primary.blockId||alt.name.toLowerCase()!==primary.name.toLowerCase()||alt.source.pageIndex!==primary.source.pageIndex||alt.source.startByte>primary.source.startByte||alt.source.endByte<primary.source.endByte)fail();
        const agrees=semantics.every(k=>alt[k]===primary[k]);
        if(v.status!==(agrees?'AGREES':'DISAGREES')||v.reason!==(agrees?'MATCH':'SEMANTIC_DISAGREEMENT'))fail();
      }else if(v.status!=='UNRESOLVED'||!['INVALID_EVIDENCE','INSUFFICIENT_EVIDENCE','INVALID_RESPONSE'].includes(v.reason))fail();
      const f=extraction.facts[index];
      if(f.type!==(v.status==='AGREES'?restored.facts[index].type:'OBSERVATION')||f.assertionStatus!==(v.status==='AGREES'?restored.facts[index].assertionStatus:'UNKNOWN'))fail();
    }
  }catch{fail();}
}
