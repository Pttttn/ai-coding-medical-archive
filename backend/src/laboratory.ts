import {TextDecoder} from 'node:util';
import {AiError} from './core';
import {irHash,SourceIR} from './source-ir';

type Span={pageIndex:number;startByte:number;endByte:number};
export type Laboratory={schemaVersion:'lab-rows-v1';sourceIRHash:string;sourceHash:string;artifactHash:string;
  coverage:'SUPPORTED_ROWS_ONLY';candidateRows:number;
  rows:{name:string;result:{raw:string;kind:'NUMERIC'|'QUALITATIVE';comparator:string|null;numericValue:string|null};unit:string|null;referenceRaw:string|null;subject:'PATIENT'|'UNKNOWN';source:Span;sourceText:string}[];
  dates:{role:'RESULT'|'SPECIMEN'|'STUDY';iso:string;raw:string;source:Span}[];
  subjectSources:Span[];issues:{code:string;source:Span|null}[]};

// Internal boundary checks: source/version, byte ranges and exact legacy projection.
// Medical/layout classification is performed by the versioned Python annotator.
export function validateLaboratory(lab:Laboratory,ir:SourceIR|undefined,facts:any[]):void {
  const fail=()=>{throw new AiError('LAB_ARTIFACT_INVALID');};
  const decoder=new TextDecoder('utf8',{fatal:true});
  try {
    if(!ir||!lab||lab.schemaVersion!=='lab-rows-v1'||lab.sourceIRHash!==ir.irHash||lab.sourceHash!==ir.sourceHash||lab.coverage!=='SUPPORTED_ROWS_ONLY')fail();
    const {artifactHash,...body}=lab;
    if(artifactHash!==irHash(body)||!Array.isArray(lab.rows)||lab.rows.length>200||!Array.isArray(lab.dates)||!Array.isArray(lab.subjectSources)||!Array.isArray(lab.issues)||!Number.isInteger(lab.candidateRows)||lab.candidateRows<lab.rows.length||facts.length!==lab.rows.length)fail();
    const resolve=(span:Span)=>{
      if(!span||![span.pageIndex,span.startByte,span.endByte].every(Number.isSafeInteger)||span.pageIndex<0||span.pageIndex>=ir!.pages.length||span.startByte<0||span.endByte<=span.startByte)fail();
      const bytes=Buffer.from(ir!.pages[span.pageIndex].text);
      if(span.endByte>bytes.length)fail();
      return decoder.decode(bytes.subarray(span.startByte,span.endByte));
    };
    const dates=new Set(lab.dates.filter(d=>d.role==='RESULT').map(d=>d.iso));
    const eventDate=dates.size===1?[...dates][0]:null;
    for(const d of lab.dates){
      const normalized=/^\d{2}\.\d{2}\.\d{4}$/.test(d.raw)?d.raw.split('.').reverse().join('-'):d.raw;
      if(!['RESULT','SPECIMEN','STUDY'].includes(d.role)||!/^\d{4}-\d{2}-\d{2}$/.test(d.iso)||d.iso!==normalized||new Date(d.iso).toISOString().slice(0,10)!==d.iso||!resolve(d.source).includes(d.raw))fail();
    }
    for(const span of lab.subjectSources)if(!['субъект: пациент','subject: patient'].includes(resolve(span).trim().toLowerCase()))fail();
    for(const issue of lab.issues){if(!['UNSUPPORTED_ROW','DATE_CONFLICT','INVALID_DATE','ROW_LIMIT','UNSUPPORTED_CONTENT'].includes(issue.code))fail();if(issue.source)resolve(issue.source);}
    const seen=new Set<string>();
    for(let index=0;index<lab.rows.length;index++){
      const row=lab.rows[index],f=facts[index],r=row.result;
      const key=JSON.stringify(row.source);
      if(seen.has(key))fail();seen.add(key);
      if(resolve(row.source)!==row.sourceText||typeof row.name!=='string'||!row.name||!row.sourceText.includes(row.name)||!row.sourceText.includes(r.raw)||!['PATIENT','UNKNOWN'].includes(row.subject)||(row.subject==='PATIENT'&&!lab.subjectSources.length))fail();
      if(row.unit!==null&&(typeof row.unit!=='string'||!row.sourceText.includes(row.unit)))fail();
      if(row.referenceRaw!==null&&(typeof row.referenceRaw!=='string'||!row.sourceText.includes(row.referenceRaw)))fail();
      if(r.kind==='NUMERIC'){
        const match=r.raw.match(/^(<=|>=|≤|≥|<|>|=)?\s*([+−-]?\d+(?:[.,]\d+)?(?:[eE][+-]?\d+)?)$/);
        if(!match||typeof r.numericValue!=='string'||!Number.isFinite(Number(r.numericValue))||Number(match[2].replace(',','.').replace('−','-'))!==Number(r.numericValue)||(({ '≤':'<=','≥':'>=' } as Record<string,string>)[match[1]]??match[1]??'=')!==r.comparator)fail();
      }else if(r.kind!=='QUALITATIVE'||r.comparator!==null||r.numericValue!==null||!['положительно','отрицательно','не обнаружено','обнаружено','positive','negative'].includes(r.raw.toLowerCase()))fail();
      const number=r.comparator==='='?Number(r.numericValue):null;
      if(f.type!=='LAB_RESULT'||f.name!==row.name||f.valueText!==row.sourceText||f.valueNumber!==number||f.unit!==row.unit||f.eventDate!==eventDate||f.assertionStatus!=='CONFIRMED'||f.confidence!==null||f.provenance?.sourceText!==row.sourceText||f.provenance?.page!==ir!.pages[row.source.pageIndex].pageNumber)fail();
    }
  } catch {fail();}
}
