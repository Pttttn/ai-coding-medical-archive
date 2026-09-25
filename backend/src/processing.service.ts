import {SourceIR,validateSourceIR} from './source-ir';
import {Laboratory,validateLaboratory} from './laboratory';
import {Injectable,OnApplicationBootstrap,OnApplicationShutdown} from '@nestjs/common';
import {DataSource} from 'typeorm';
import {AiClient,AiError,normalizeTags} from './core';
import {audit,ensureTags,factSnapshot,rebuildTimeline} from './archive.service';
import {ASSERTION_STATUSES,Document,DOCUMENT_TYPES,ExtractionRun,FACT_TYPES,FactProvenance,MedicalFact,Page,ProcessingJob,TextRevision} from './entities';

type ExtractedFact={type:string;name:string;valueText:string|null;valueNumber:number|null;unit:string|null;eventDate:string|null;assertionStatus:string;confidence:number|null;provenance:{page:number|null;sourceText:string}};
export interface ProcessResult {
  text:string;pages:Page[];sourceIR?:SourceIR;laboratory?:Laboratory|null;extractionProfile?:string;
  extraction:{documentType:string;documentDate:string|null;summary:string;tags:string[];facts:ExtractedFact[]};
  warnings?:string[];model?:string;modelDigest?:string;promptVersion?:string;schemaVersion?:string;parserVersion?:string;
}
const norm=(s:string)=>s.replace(/\s+/g,' ').trim();
const isDate=(s:unknown)=>s===null||s===undefined||(typeof s==='string'&&/^\d{4}-\d{2}-\d{2}$/.test(s)&&!Number.isNaN(Date.parse(s))&&new Date(s).toISOString().slice(0,10)===s);
export function validateExtraction(r:ProcessResult):void {
  const invalid=()=>{throw new AiError('EXTRACTION_INVALID');};
  if(!r||typeof r.text!=='string'||!r.text.trim()||r.text.length>2_000_000||!Array.isArray(r.pages)||!r.extraction)invalid();
  if(r.pages.some(p=>(p.pageNumber!==null&&(!Number.isInteger(p.pageNumber)||p.pageNumber<1))||typeof p.text!=='string'))invalid();
  const e=r.extraction;
  if(!(DOCUMENT_TYPES as readonly string[]).includes(e.documentType)||!isDate(e.documentDate)||typeof e.summary!=='string'||e.summary.length>20000||!Array.isArray(e.tags)||e.tags.length>50||e.tags.some(t=>typeof t!=='string'||t.length>80)||!Array.isArray(e.facts)||e.facts.length>500)invalid();
  for(const f of e.facts) {
    if(!f||!(FACT_TYPES as readonly string[]).includes(f.type)||typeof f.name!=='string'||!f.name.trim()||f.name.length>300||!isDate(f.eventDate)||!(ASSERTION_STATUSES as readonly string[]).includes(f.assertionStatus??'UNKNOWN'))invalid();
    if(f.valueText!=null&&(typeof f.valueText!=='string'||f.valueText.length>10000))invalid();
    if(f.valueNumber!=null&&(typeof f.valueNumber!=='number'||!Number.isFinite(f.valueNumber)))invalid();
    if(f.unit!=null&&(typeof f.unit!=='string'||f.unit.length>100))invalid();
    if(f.confidence!=null&&(typeof f.confidence!=='number'||f.confidence<0||f.confidence>1))invalid();
    if(!f.provenance||typeof f.provenance.sourceText!=='string'||!f.provenance.sourceText.trim()||!norm(r.text).includes(norm(f.provenance.sourceText)))invalid();
    if(f.provenance.page!=null&&(!Number.isInteger(f.provenance.page)||!r.pages.some(p=>p.pageNumber===f.provenance.page&&norm(p.text).includes(norm(f.provenance.sourceText)))))invalid();
  }
}
export function sameReviewedFact(f:MedicalFact,incoming:ExtractedFact):boolean {
  const original=f.originalValue as any;
  return [f,original].some(v=>v?.type===incoming.type&&norm(String(v.name)).toLocaleLowerCase()===norm(incoming.name).toLocaleLowerCase()&&(v.eventDate??null)===(incoming.eventDate??null));
}

@Injectable()
export class ProcessingService implements OnApplicationBootstrap,OnApplicationShutdown {
  private timer:ReturnType<typeof setInterval>|undefined;
  private running=false;
  private stopping=false;
  constructor(private readonly db:DataSource,private readonly ai:AiClient){}
  async onApplicationBootstrap() {
    if(process.env.WORKER_ENABLED==='false')return;
    await this.db.query("UPDATE processing_jobs SET status='QUEUED',\"errorCode\"='INTERRUPTED_RETRY',\"availableAt\"=NULL WHERE status='RUNNING'");
    await this.db.query("UPDATE extraction_runs SET status='INTERRUPTED',\"validationErrors\"='[\"INTERRUPTED_RETRY\"]'::jsonb,\"completedAt\"=now() WHERE status='RUNNING'");
    this.timer=setInterval(()=>{void this.tick();},1000);
    this.timer.unref();void this.tick();
  }
  async onApplicationShutdown(){this.stopping=true;if(this.timer)clearInterval(this.timer);}
  async tick() {
    if(this.running||this.stopping)return;
    this.running=true;
    try {
      const jobs=await this.db.query("WITH claimed AS (UPDATE processing_jobs SET status='RUNNING',attempt=attempt+1,\"updatedAt\"=now() WHERE id=(SELECT id FROM processing_jobs WHERE status='QUEUED' AND (\"availableAt\" IS NULL OR \"availableAt\"<=now()) ORDER BY \"createdAt\" FOR UPDATE SKIP LOCKED LIMIT 1) RETURNING *) SELECT * FROM claimed");
      if(jobs[0])await this.run(jobs[0]);
    }catch{/* Never log medical content or DB parameter values. Next poll retries acquisition. */}
    finally{this.running=false;}
  }
  async run(job:ProcessingJob) {
    let run:ExtractionRun|undefined;
    try {
      const doc=await this.db.getRepository(Document).createQueryBuilder('d').addSelect('d.storagePath').where('d.id=:id',{id:job.documentId}).getOne();
      if(!doc||doc.generation!==job.generation||(doc.deletedAt&&job.operation!=='REMOVE')) {
        await this.db.getRepository(ProcessingJob).update(job.id,{status:'SUPERSEDED'});return;
      }
      if(job.operation==='REMOVE') {
        if(doc.deletedAt)await this.ai.call('remove',{documentId:doc.id});
        await this.db.getRepository(ProcessingJob).update(job.id,{status:'READY',errorCode:null});return;
      }
      let revision=await this.db.getRepository(TextRevision).findOneBy({documentId:doc.id,version:doc.textVersion});
      if(job.operation==='PROCESS') {
        await this.setStatus(doc.id,job.generation,revision?'EXTRACTING':'PARSING');
        run=await this.db.getRepository(ExtractionRun).save({documentId:doc.id,textVersion:revision?.version??1,status:'RUNNING',validationErrors:[]});
        const result=await this.ai.call<ProcessResult>('process',{documentId:doc.id,version:revision?.version??1,title:doc.title,...(doc.sourceType==='PDF'&&revision?.parser!=='user-edit'?{filePath:doc.storagePath}:revision?{text:revision.content}:{filePath:doc.storagePath})});
        await this.db.getRepository(ExtractionRun).update(run.id,{rawJson:result as any,model:result.model??null,modelDigest:result.modelDigest??null,promptVersion:result.promptVersion??null,schemaVersion:result.schemaVersion??null,parserVersion:result.parserVersion??null});
        validateExtraction(result);
        if(result.sourceIR!==undefined){
          validateSourceIR(result.sourceIR,doc.id,result.pages);
          if(result.text!==result.pages.map(p=>p.text).join('\n\n'))throw new AiError('SOURCE_IR_INVALID');
        }
        if(result.laboratory!=null)validateLaboratory(result.laboratory,result.sourceIR,result.extraction.facts);
        const applied=await this.db.transaction(async m=>{
          const current=await m.getRepository(Document).findOne({where:{id:doc.id},lock:{mode:'pessimistic_write'}});
          if(!current||current.deletedAt||current.generation!==job.generation)return false;
          if(!revision||revision.content!==result.text||JSON.stringify(revision.pages.length?revision.pages:[{pageNumber:null,text:revision.content}])!==JSON.stringify(result.pages)) {
            current.textVersion++;
            revision=await m.save(TextRevision,m.create(TextRevision,{documentId:doc.id,version:current.textVersion,content:result.text,pages:result.pages,parser:'pypdf',parserVersion:result.parserVersion??'unknown'}));
          }
          if(result.sourceIR)await m.query('INSERT INTO source_ir_revisions ("documentId","textRevisionId","irHash","schemaVersion",content) VALUES ($1,$2,$3,$4,$5::jsonb) ON CONFLICT ("textRevisionId","irHash") DO NOTHING',[doc.id,revision!.id,result.sourceIR.irHash,result.sourceIR.schemaVersion,JSON.stringify(result.sourceIR)]);
          const preserved=await m.getRepository(MedicalFact).createQueryBuilder('f').where('f."documentId"=:id AND f.active = true AND f."reviewStatus" <> :status',{id:doc.id,status:'UNREVIEWED'}).getMany();
          await m.update(MedicalFact,{documentId:doc.id,reviewStatus:'UNREVIEWED',active:true},{active:false});
          for(const incoming of result.extraction.facts) {
            if(preserved.some(f=>sameReviewedFact(f,incoming)))continue;
            const f=m.create(MedicalFact,{documentId:doc.id,type:incoming.type,name:incoming.name,valueText:incoming.valueText??null,valueNumber:incoming.valueNumber??null,unit:incoming.unit??null,eventDate:incoming.eventDate??null,assertionStatus:incoming.assertionStatus??'UNKNOWN',reviewStatus:'UNREVIEWED',confidence:incoming.confidence??null,originalValue:{},active:true});
            f.originalValue=factSnapshot(f);await m.save(f);
            await m.save(FactProvenance,m.create(FactProvenance,{factId:f.id,documentId:doc.id,textRevisionId:revision!.id,textVersion:revision!.version,pageNumber:incoming.provenance.page??null,sourceText:incoming.provenance.sourceText}));
          }
          if(!['NOTE','VISIT_TRANSCRIPT'].includes(current.documentType))current.documentType=result.extraction.documentType;
          if(!current.documentDate)current.documentDate=result.extraction.documentDate??null;
          current.summary=result.extraction.summary;
          current.tags=normalizeTags([...current.tags,...result.extraction.tags]);await ensureTags(m,current.tags);
          current.searchText=[current.title,current.summary,revision!.content].join('\n');current.status='INDEXING';
          await m.save(current);await rebuildTimeline(m,current);
          await m.update(ExtractionRun,run!.id,{textVersion:revision!.version,model:result.model??'unknown',modelDigest:result.modelDigest??null,promptVersion:result.promptVersion??'unknown',schemaVersion:result.schemaVersion??'unknown',parserVersion:result.parserVersion??'unknown',status:'READY',rawJson:result as any,completedAt:new Date()});
          await audit(m,doc.id,'DOCUMENT',doc.id,'EXTRACTION_COMPLETED',null,{runId:run!.id,textVersion:revision!.version});
          return true;
        });
        if(!applied){await this.db.getRepository(ExtractionRun).update(run.id,{status:'SUPERSEDED',completedAt:new Date()});await this.db.getRepository(ProcessingJob).update(job.id,{status:'SUPERSEDED'});return;}
      }
      if(!revision)throw new AiError('TEXT_UNAVAILABLE');
      const current=await this.db.getRepository(Document).findOneByOrFail({id:doc.id});
      if(current.deletedAt||current.generation!==job.generation){await this.db.getRepository(ProcessingJob).update(job.id,{status:'SUPERSEDED'});return;}
      await this.setStatus(doc.id,job.generation,'INDEXING');
      const corrections=await this.db.getRepository(MedicalFact).createQueryBuilder('f').where('f."documentId"=:id AND f.active=true AND f."reviewStatus"<>:status',{id:doc.id,status:'UNREVIEWED'}).getMany();
      await this.ai.call('index',{documentId:doc.id,title:current.title,version:revision.version,text:revision.content,pages:revision.pages,corrections:corrections.map(f=>({id:f.id,name:f.name,valueText:f.valueText,valueNumber:f.valueNumber,unit:f.unit,reviewStatus:f.reviewStatus}))});
      await this.db.transaction(async m=>{
        const locked=await m.getRepository(Document).findOne({where:{id:doc.id},lock:{mode:'pessimistic_write'}});
        if(!locked||locked.deletedAt||locked.generation!==job.generation){await m.update(ProcessingJob,job.id,{status:'SUPERSEDED'});return;}
        locked.status='READY';locked.errorCode=null;await m.save(locked);
        await m.update(ProcessingJob,job.id,{status:'READY',errorCode:null});
        await audit(m,doc.id,'DOCUMENT',doc.id,'INDEXING_COMPLETED',null,{textVersion:revision!.version});
      });
    }catch(e) {
      const code=e instanceof AiError?e.safeCode:'PROCESSING_FAILED';
      if(run)await this.db.getRepository(ExtractionRun).update({id:run.id,status:'RUNNING'},{status:'FAILED',validationErrors:[code],completedAt:new Date()});
      const transient=['AI_UNAVAILABLE','MODEL_UNAVAILABLE','EMBEDDING_UNAVAILABLE','INDEX_UNAVAILABLE'].includes(code);
      const retry=job.operation==='REMOVE'||(transient&&job.attempt<3);
      await this.db.getRepository(ProcessingJob).update(job.id,{status:retry?'QUEUED':'FAILED',errorCode:code,availableAt:retry?new Date(Date.now()+Math.min(job.attempt*15000,60000)):null});
      if(!retry||job.operation!=='REMOVE') await this.db.getRepository(Document).createQueryBuilder().update().set({status:code==='UNSUPPORTED_OCR_REQUIRED'?'UNSUPPORTED_OCR_REQUIRED':retry?'UPLOADED':'FAILED',errorCode:code}).where('id=:id AND generation=:generation AND "deletedAt" IS NULL',{id:job.documentId,generation:job.generation}).execute();
      if(!retry)await audit(this.db.manager,job.documentId,'DOCUMENT',job.documentId,'PROCESSING_FAILED',null,{code,jobId:job.id});
    }
  }
  private async setStatus(id:string,generation:number,status:string){await this.db.getRepository(Document).update({id,generation},{status});}
}
