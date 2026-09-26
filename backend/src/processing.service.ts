import {Visit,validateVisit} from './visit';
import {irHash,SourceIR,validateSourceIR} from './source-ir';
import {confirmIndexSettings,expectedIndexSettings,ParseRecipe,validateParseRecipe,validateProcessingRecipe} from './recipe';
import {Laboratory,validateLaboratory} from './laboratory';
import {Injectable,OnApplicationBootstrap,OnApplicationShutdown} from '@nestjs/common';
import {DataSource,EntityManager,In} from 'typeorm';
import {AiClient,AiError,normalizeTags} from './core';
import {audit,ensureTags,factSnapshot,rebuildTimeline,storedParse} from './archive.service';
import {ASSERTION_STATUSES,Document,DOCUMENT_TYPES,ExtractionRun,FACT_TYPES,FactProvenance,MedicalFact,Page,ProcessingJob,ProcessingRevision,TextRevision} from './entities';

type ExtractedFact={type:string;name:string;valueText:string|null;valueNumber:number|null;unit:string|null;eventDate:string|null;assertionStatus:string;confidence:number|null;provenance:{page:number|null;sourceText:string}};
export interface ProcessResult {
  text:string;pages:Page[];sourceIR?:SourceIR;laboratory?:Laboratory|null;visit?:Visit|null;extractionProfile?:string;processingRecipe?:Record<string,unknown>;
  extraction:{documentType:string;documentDate:string|null;summary:string;tags:string[];facts:ExtractedFact[]};
  warnings?:string[];model?:string;modelDigest?:string;promptVersion?:string;schemaVersion?:string;parserVersion?:string;
}
export interface ParseResult {text:string;pages:Page[];sourceIR:SourceIR;parseRecipe:ParseRecipe;warnings?:string[];parserVersion?:string}
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

/** Locks the document with every column: saving an entity loaded without select:false storagePath would clear it. */
const lockDocument=(m:EntityManager,id:string)=>m.getRepository(Document).createQueryBuilder('d').addSelect('d.storagePath').where('d.id=:id',{id}).setLock('pessimistic_write').getOne();
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
    let run:ExtractionRun|undefined,preparedId:string|null=null;
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
      let prepared:ProcessingRevision|null=null;
      if(job.operation==='PROCESS') {
        const stage=await this.parseStage(job,doc,revision);
        if(!stage){await this.db.getRepository(ProcessingJob).update(job.id,{status:'SUPERSEDED'});return;}
        revision=stage.revision;
        prepared=await this.reusablePrepared(job,revision);
        if(!prepared) {
          await this.setStatus(doc.id,job.generation,'EXTRACTING');
          run=await this.db.getRepository(ExtractionRun).save({documentId:doc.id,textVersion:revision.version,sourceIrRevisionId:stage.id,status:'RUNNING',validationErrors:[]});
          const result=await this.ai.call<ProcessResult>('process',{documentId:doc.id,version:revision.version,title:doc.title,sourceIR:stage.ir});
          result.warnings=[...stage.warnings,...(Array.isArray(result.warnings)?result.warnings:[])];
          await this.db.getRepository(ExtractionRun).update(run.id,{rawJson:result as any,model:result.model??null,modelDigest:result.modelDigest??null,promptVersion:result.promptVersion??null,schemaVersion:result.schemaVersion??null,parserVersion:result.parserVersion??null});
          validateExtraction(result);
          // Extraction must be a projection of exactly the stored parse stage, never a re-parse.
          if(result.text!==revision.content||irHash(result.pages)!==stage.ir.sourceHash||(result.sourceIR!==undefined&&result.sourceIR.irHash!==stage.ir.irHash))throw new AiError('SOURCE_IR_INVALID');
          result.sourceIR=stage.ir;
          const recipeHash=validateProcessingRecipe(result.processingRecipe,stage.parseRecipeHash);
          if(result.laboratory!=null&&result.visit!=null)throw new AiError('VISIT_ARTIFACT_INVALID');
          if(result.visit!=null)validateVisit(result.visit,result.sourceIR,result.extraction);
          if(result.laboratory!=null)validateLaboratory(result.laboratory,result.sourceIR,result.extraction.facts);
          // Prepare: new facts are stored inactive under a new revision; the active snapshot is untouched.
          prepared=await this.db.transaction(async m=>{
            const current=await lockDocument(m,doc.id);
            if(!current||current.deletedAt||current.generation!==job.generation||current.textVersion!==revision!.version)return null;
            const rev=await m.save(ProcessingRevision,m.create(ProcessingRevision,{documentId:doc.id,sourceIrRevisionId:stage.id,textRevisionId:revision!.id,extractionRunId:run!.id,recipeHash,status:'PREPARED'}));
            for(const incoming of result.extraction.facts) {
              const f=m.create(MedicalFact,{documentId:doc.id,type:incoming.type,name:incoming.name,valueText:incoming.valueText??null,valueNumber:incoming.valueNumber??null,unit:incoming.unit??null,eventDate:incoming.eventDate??null,assertionStatus:incoming.assertionStatus??'UNKNOWN',reviewStatus:'UNREVIEWED',confidence:incoming.confidence??null,originalValue:{},active:false,processingRevisionId:rev.id});
              f.originalValue=factSnapshot(f);await m.save(f);
              await m.save(FactProvenance,m.create(FactProvenance,{factId:f.id,documentId:doc.id,textRevisionId:revision!.id,textVersion:revision!.version,pageNumber:incoming.provenance.page??null,sourceText:incoming.provenance.sourceText}));
            }
            await m.update(ExtractionRun,run!.id,{textVersion:revision!.version,model:result.model??'unknown',modelDigest:result.modelDigest??null,promptVersion:result.promptVersion??'unknown',schemaVersion:result.schemaVersion??'unknown',parserVersion:result.parserVersion??'unknown',status:'READY',rawJson:result as any,recipeHash,completedAt:new Date()});
            await m.update(ProcessingJob,job.id,{processingRevisionId:rev.id});
            await audit(m,doc.id,'DOCUMENT',doc.id,'EXTRACTION_COMPLETED',null,{runId:run!.id,textVersion:revision!.version,processingRevisionId:rev.id});
            return rev;
          });
          if(!prepared){await this.db.getRepository(ExtractionRun).update(run.id,{status:'SUPERSEDED',completedAt:new Date()});await this.db.getRepository(ProcessingJob).update(job.id,{status:'SUPERSEDED'});return;}
        }
        preparedId=prepared.id;
      }
      if(!revision)throw new AiError('TEXT_UNAVAILABLE');
      const current=await this.db.getRepository(Document).findOneByOrFail({id:doc.id});
      if(current.deletedAt||current.generation!==job.generation){await this.db.getRepository(ProcessingJob).update(job.id,{status:'SUPERSEDED'});return;}
      // PROCESS stages the prepared revision; INDEX re-stages the active one (or legacy chunks without revision).
      const target=prepared??(current.activeProcessingRevisionId?await this.db.getRepository(ProcessingRevision).findOneBy({id:current.activeProcessingRevisionId}):null);
      // A revision's chunks are built from its own text; an active revision of an earlier text waits for its PROCESS job.
      if(target&&!prepared&&target.textRevisionId!==revision.id){await this.db.getRepository(ProcessingJob).update(job.id,{status:'SUPERSEDED'});return;}
      await this.setStatus(doc.id,job.generation,'INDEXING');
      const expected=target?expectedIndexSettings((await this.db.getRepository(ExtractionRun).findOneByOrFail({id:target.extractionRunId})).rawJson):null;
      const corrections=await this.db.getRepository(MedicalFact).createQueryBuilder('f').where('f."documentId"=:id AND f.active=true AND f."reviewStatus"<>:status',{id:doc.id,status:'UNREVIEWED'}).getMany();
      const manifest=await this.ai.call<{revisionId?:string|null;documentChunks?:number;contentHash?:string;indexSettings?:unknown}>('index',{documentId:doc.id,title:current.title,version:revision.version,text:revision.content,pages:revision.pages,corrections:corrections.map(f=>({id:f.id,name:f.name,valueText:f.valueText,valueNumber:f.valueNumber,unit:f.unit,reviewStatus:f.reviewStatus})),...(target?{revisionId:target.id}:{}),...(expected?{expectedIndexSettings:expected}:{})});
      if(target&&(manifest?.revisionId!==target.id||!Number.isSafeInteger(manifest.documentChunks)||manifest.documentChunks!<0))throw new AiError('INDEX_MANIFEST_INVALID');
      // The indexer reports the settings it used; they must be the ones the extraction recipe named.
      if(expected)confirmIndexSettings(expected,manifest.indexSettings);
      const activated=await this.db.transaction(async m=>{
        const locked=await lockDocument(m,doc.id);
        if(!locked||locked.deletedAt||locked.generation!==job.generation){await m.update(ProcessingJob,job.id,{status:'SUPERSEDED'});return false;}
        if(prepared) {
          const rev=await m.getRepository(ProcessingRevision).findOne({where:{id:prepared.id},lock:{mode:'pessimistic_write'}});
          if(!rev||rev.status!=='PREPARED'||locked.textVersion!==revision!.version||rev.textRevisionId!==revision!.id){await m.update(ProcessingJob,job.id,{status:'SUPERSEDED'});return false;}
          await this.activate(m,locked,rev,{revisionId:rev.id,documentChunks:manifest.documentChunks!,contentHash:manifest.contentHash??null,indexSettings:expected});
        }
        locked.status='READY';locked.errorCode=null;await m.save(locked);
        await m.update(ProcessingJob,job.id,{status:'READY',errorCode:null});
        await audit(m,doc.id,'DOCUMENT',doc.id,'INDEXING_COMPLETED',null,{textVersion:revision!.version,processingRevisionId:target?.id??null});
        return true;
      });
      // Older chunk sets are unreadable once the pointer moved; removing them is only cleanup.
      if(activated&&prepared)await this.ai.call('prune',{documentId:doc.id,keepRevisionId:prepared.id}).catch(()=>undefined);
    }catch(e) {
      const code=e instanceof AiError?e.safeCode:'PROCESSING_FAILED';
      if(run)await this.db.getRepository(ExtractionRun).update({id:run.id,status:'RUNNING'},{status:'FAILED',validationErrors:[code],completedAt:new Date()});
      const transient=['AI_UNAVAILABLE','MODEL_UNAVAILABLE','EMBEDDING_UNAVAILABLE','INDEX_UNAVAILABLE'].includes(code);
      const retry=job.operation==='REMOVE'||(transient&&job.attempt<3);
      await this.db.getRepository(ProcessingJob).update(job.id,{status:retry?'QUEUED':'FAILED',errorCode:code,availableAt:retry?new Date(Date.now()+Math.min(job.attempt*15000,60000)):null});
      if(!retry||job.operation!=='REMOVE') await this.db.getRepository(Document).createQueryBuilder().update().set({status:code==='UNSUPPORTED_OCR_REQUIRED'?'UNSUPPORTED_OCR_REQUIRED':retry?'UPLOADED':'FAILED',errorCode:code}).where('id=:id AND generation=:generation AND "deletedAt" IS NULL',{id:job.documentId,generation:job.generation}).execute();
      // A prepared revision that will not be retried never becomes visible.
      if(!retry&&preparedId)await this.db.getRepository(ProcessingRevision).update({id:preparedId,status:'PREPARED'},{status:'FAILED'});
      if(!retry)await audit(this.db.manager,job.documentId,'DOCUMENT',job.documentId,'PROCESSING_FAILED',null,{code,jobId:job.id});
    }
  }
  /** A retry of the same job continues from its prepared revision instead of extracting again. */
  private async reusablePrepared(job:ProcessingJob,revision:TextRevision):Promise<ProcessingRevision|null> {
    if(!job.processingRevisionId)return null;
    return this.db.getRepository(ProcessingRevision).findOneBy({id:job.processingRevisionId,documentId:job.documentId,textRevisionId:revision.id,status:'PREPARED'});
  }
  /** Switches the document's snapshot: facts, summary, timeline and the readable index revision change together. */
  private async activate(m:EntityManager,doc:Document,rev:ProcessingRevision,indexManifest:NonNullable<ProcessingRevision['indexManifest']>) {
    const run=await m.findOneByOrFail(ExtractionRun,{id:rev.extractionRunId});
    const extraction=(run.rawJson as ProcessResult).extraction;
    // Reviewed facts are the user's overlay and stay; a new fact duplicating one of them stays inactive.
    const preserved=await m.getRepository(MedicalFact).createQueryBuilder('f').where('f."documentId"=:id AND f.active = true AND f."reviewStatus" <> :status',{id:doc.id,status:'UNREVIEWED'}).getMany();
    await m.update(MedicalFact,{documentId:doc.id,reviewStatus:'UNREVIEWED',active:true},{active:false});
    const incoming=await m.find(MedicalFact,{where:{processingRevisionId:rev.id}});
    const visible=incoming.filter(f=>!preserved.some(p=>sameReviewedFact(p,f as unknown as ExtractedFact)));
    if(visible.length)await m.update(MedicalFact,{id:In(visible.map(f=>f.id))},{active:true});
    await m.update(ProcessingRevision,{documentId:doc.id,status:'ACTIVE'},{status:'SUPERSEDED'});
    await m.update(ProcessingRevision,rev.id,{status:'ACTIVE',activatedAt:new Date(),indexManifest});
    const text=await m.findOneByOrFail(TextRevision,{id:rev.textRevisionId});
    if(!['NOTE','VISIT_TRANSCRIPT'].includes(doc.documentType))doc.documentType=extraction.documentType;
    if(!doc.documentDate)doc.documentDate=extraction.documentDate??null;
    doc.summary=extraction.summary;
    doc.tags=normalizeTags([...doc.tags,...extraction.tags]);await ensureTags(m,doc.tags);
    doc.searchText=[doc.title,doc.summary,text.content].join('\n');
    doc.activeProcessingRevisionId=rev.id;
    await m.save(doc);await rebuildTimeline(m,doc);
    await audit(m,doc.id,'DOCUMENT',doc.id,'PROCESSING_REVISION_ACTIVATED',null,{processingRevisionId:rev.id,facts:visible.length,chunks:indexManifest.documentChunks});
  }
  /** Deterministic parse stage, committed before any model call. A retry of the same job reuses it. */
  private async parseStage(job:ProcessingJob,doc:Document,revision:TextRevision|null):Promise<{id:string;ir:SourceIR;parseRecipeHash:string;revision:TextRevision;warnings:string[]}|null> {
    if(job.sourceIrRevisionId&&revision) {
      const [row]=await this.db.query('SELECT id,content,"parseRecipeHash" FROM source_ir_revisions WHERE id=$1 AND "documentId"=$2 AND "textRevisionId"=$3',[job.sourceIrRevisionId,doc.id,revision.id]);
      if(row?.parseRecipeHash)return {id:row.id,ir:row.content,parseRecipeHash:row.parseRecipeHash,revision,warnings:[]};
    }
    // CURRENT_TEXT reuses the stored parse of the current text; the next stage re-verifies it before extraction.
    if(job.parseSource==='CURRENT_TEXT'&&revision) {
      const stored=await storedParse(this.db.manager,revision.id);
      if(stored)return this.db.transaction(async m=>{
        const current=await lockDocument(m,doc.id);
        if(!current||current.deletedAt||current.generation!==job.generation||current.textVersion!==revision.version)return null;
        await m.update(ProcessingJob,job.id,{sourceIrRevisionId:stored.id});
        await audit(m,doc.id,'DOCUMENT',doc.id,'PARSE_REUSED',null,{jobId:job.id,textVersion:revision.version,parseRecipeHash:stored.parseRecipeHash});
        return {id:stored.id,ir:stored.content,parseRecipeHash:stored.parseRecipeHash,revision,warnings:[]};
      });
      // Parsing a paged text again as plain text would lose its pages.
      if(revision.pages.length)throw new AiError('REPROCESS_MODE_UNAVAILABLE');
    }
    if(job.parseSource==='ORIGINAL'&&!doc.storagePath)throw new AiError('REPROCESS_MODE_UNAVAILABLE');
    const input=job.parseSource==='ORIGINAL'?{filePath:doc.storagePath}:job.parseSource==='CURRENT_TEXT'&&revision?{text:revision.content}
      :doc.sourceType==='PDF'&&revision?.parser!=='user-edit'?{filePath:doc.storagePath}:revision?{text:revision.content}:{filePath:doc.storagePath};
    await this.setStatus(doc.id,job.generation,'PARSING');
    const parsed=await this.ai.call<ParseResult>('parse',{documentId:doc.id,version:revision?.version??1,title:doc.title,...input});
    if(!parsed||typeof parsed.text!=='string'||!parsed.text.trim()||parsed.text.length>2_000_000||!Array.isArray(parsed.pages)||!parsed.pages.length)throw new AiError('SOURCE_IR_INVALID');
    validateSourceIR(parsed.sourceIR,doc.id,parsed.pages);
    if(parsed.text!==parsed.pages.map(p=>p.text).join('\n\n'))throw new AiError('SOURCE_IR_INVALID');
    validateParseRecipe(parsed.parseRecipe,parsed.sourceIR);
    const warnings=Array.isArray(parsed.warnings)?parsed.warnings.filter((w):w is string=>typeof w==='string'):[];
    return this.db.transaction(async m=>{
      const current=await lockDocument(m,doc.id);
      if(!current||current.deletedAt||current.generation!==job.generation)return null;
      let stored=await m.getRepository(TextRevision).findOneBy({documentId:doc.id,version:current.textVersion});
      if(!stored||stored.content!==parsed.text||JSON.stringify(stored.pages.length?stored.pages:[{pageNumber:null,text:stored.content}])!==JSON.stringify(parsed.pages)) {
        current.textVersion++;await m.save(current);
        stored=await m.save(TextRevision,m.create(TextRevision,{documentId:doc.id,version:current.textVersion,content:parsed.text,pages:parsed.pages,parser:'pypdf',parserVersion:parsed.sourceIR.parserVersion}));
      }
      const ir=parsed.sourceIR,recipe=parsed.parseRecipe;
      await m.query('INSERT INTO source_ir_revisions ("documentId","textRevisionId","irHash","schemaVersion",content,"parseRecipe","parseRecipeHash") VALUES ($1,$2,$3,$4,$5::jsonb,$6::jsonb,$7) ON CONFLICT ("textRevisionId","irHash") DO NOTHING',[doc.id,stored.id,ir.irHash,ir.schemaVersion,JSON.stringify(ir),JSON.stringify(recipe),recipe.recipeHash]);
      const [row]=await m.query('SELECT id,"parseRecipeHash" FROM source_ir_revisions WHERE "textRevisionId"=$1 AND "irHash"=$2',[stored.id,ir.irHash]);
      await m.update(ProcessingJob,job.id,{sourceIrRevisionId:row.id});
      await audit(m,doc.id,'DOCUMENT',doc.id,'PARSE_COMPLETED',null,{jobId:job.id,textVersion:stored.version,parseRecipeHash:recipe.recipeHash});
      // An IR row stored before recipes were recorded keeps its immutable content; the job still names this run's recipe.
      return {id:row.id,ir,parseRecipeHash:recipe.recipeHash,revision:stored,warnings};
    });
  }
  private async setStatus(id:string,generation:number,status:string){await this.db.getRepository(Document).update({id,generation},{status});}
}
