import {Visit} from './visit';
import {BadRequestException, ConflictException, Injectable, NotFoundException} from '@nestjs/common';
import {DataSource, EntityManager, In, IsNull} from 'typeorm';
import {randomUUID,createHash} from 'node:crypto';
import {mkdir,realpath,unlink,writeFile} from 'node:fs/promises';
import {basename,resolve,relative,isAbsolute} from 'node:path';
import {AuditEvent,Document,ExtractionRun,FactProvenance,FactRevision,MedicalFact,ProcessingJob,Tag,TextRevision,TimelineEvent} from './entities';
import {CreateNoteDto,DocumentQueryDto,PaginationDto,TimelineQueryDto,UpdateDocumentDto,UpdateFactDto,UploadDto} from './dto';
import {Laboratory} from './laboratory';
import {AiClient,contentHash,normalizeTags,paginate,safeStoragePath,validatePdf} from './core';

export async function audit(m:EntityManager,documentId:string|null,entityType:string,entityId:string,action:string,before:unknown=null,after:unknown=null) {
  return m.save(AuditEvent,m.create(AuditEvent,{documentId,entityType,entityId,action,payloadBefore:before,payloadAfter:after}));
}
export async function enqueue(m:EntityManager,doc:Document,operation='PROCESS') {
  return m.save(ProcessingJob,m.create(ProcessingJob,{documentId:doc.id,operation,generation:doc.generation,status:'QUEUED'}));
}
export async function ensureTags(m:EntityManager,names:string[]) {
  for(const name of normalizeTags(names)) await m.createQueryBuilder().insert().into(Tag).values({name}).orIgnore().execute();
}
export function factSnapshot(f:MedicalFact):Record<string,unknown> {
  return {type:f.type,name:f.name,valueText:f.valueText,valueNumber:f.valueNumber,unit:f.unit,eventDate:f.eventDate,assertionStatus:f.assertionStatus,reviewStatus:f.reviewStatus};
}
export async function rebuildTimeline(m:EntityManager,doc:Document) {
  await m.delete(TimelineEvent,{documentId:doc.id});
  await m.save(TimelineEvent,m.create(TimelineEvent,{documentId:doc.id,factId:null,eventType:doc.documentType,eventDate:doc.documentDate,title:doc.title,description:doc.summary}));
  const facts=await m.find(MedicalFact,{where:{documentId:doc.id,active:true}});
  for(const f of facts.filter(f=>f.reviewStatus!=='REJECTED'))
    await m.save(TimelineEvent,m.create(TimelineEvent,{documentId:doc.id,factId:f.id,eventType:f.type,eventDate:f.eventDate,title:f.name,description:[f.valueText,f.valueNumber,f.unit].filter(v=>v!==null&&v!==undefined&&v!=='').join(' ')}));
}

@Injectable()
export class ArchiveService {
  constructor(public readonly db:DataSource,private readonly ai:AiClient){}

  async document(id:string,includeDeleted=false,m:EntityManager=this.db.manager,lock=false):Promise<Document> {
    const qb=m.getRepository(Document).createQueryBuilder('d').where('d.id = :id',{id});
    if(!includeDeleted) qb.andWhere('d."deletedAt" IS NULL');
    if(lock) qb.setLock('pessimistic_write');
    const doc=await qb.getOne();
    if(!doc) throw new NotFoundException({message:'Документ не найден',code:'DOCUMENT_NOT_FOUND'});
    return doc;
  }
  async sourceIR(id:string) {
    await this.document(id);
    const rows=await this.db.query('SELECT i.id,i."textRevisionId",i."irHash",i.content FROM source_ir_revisions i JOIN text_revisions t ON t.id=i."textRevisionId" JOIN documents d ON d.id=i."documentId" WHERE d.id=$1 AND d."deletedAt" IS NULL AND t.version=d."textVersion" ORDER BY i."createdAt" DESC,i.id LIMIT 1',[id]);
    if(!rows.length)throw new NotFoundException({message:'Исходное представление ещё не создано',code:'SOURCE_IR_UNAVAILABLE'});
    return rows[0];
  }
  async createNote(dto:CreateNoteDto) {
    return this.db.transaction(async m=>{
      const doc=await m.save(Document,m.create(Document,{title:dto.title.trim(),documentType:dto.documentType,documentDate:dto.documentDate??null,sourceType:'TEXT',sha256:contentHash(dto.text),tags:normalizeTags(dto.tags),textVersion:1,searchText:`${dto.title}\n${dto.text}`}));
      await ensureTags(m,doc.tags);
      await m.save(TextRevision,m.create(TextRevision,{documentId:doc.id,version:1,content:dto.text,pages:[],parser:'user-text'}));
      const job=await enqueue(m,doc);
      await audit(m,doc.id,'DOCUMENT',doc.id,'DOCUMENT_CREATED',null,{sourceType:'TEXT',textVersion:1});
      return {...doc,searchText:undefined,documentId:doc.id,jobId:job.id};
    });
  }
  async upload(file:Express.Multer.File|undefined,dto:UploadDto) {
    validatePdf(file);
    const root=resolve(process.env.UPLOAD_DIR??'data/uploads');
    await mkdir(root,{recursive:true});
    const storagePath=safeStoragePath(root,`${randomUUID()}.pdf`);
    await writeFile(storagePath,file.buffer,{flag:'wx',mode:0o600});
    try {
      return await this.db.transaction(async m=>{
        const doc=await m.save(Document,m.create(Document,{title:dto.title.trim(),documentType:'OTHER',documentDate:dto.documentDate??null,sourceType:'PDF',originalFilename:basename(file.originalname.replace(/\\/g,'/')).slice(0,200),storagePath,sha256:createHash('sha256').update(file.buffer).digest('hex'),mimeType:'application/pdf',tags:normalizeTags(dto.tags),searchText:dto.title}));
        await ensureTags(m,doc.tags);
        const job=await enqueue(m,doc);
        await audit(m,doc.id,'DOCUMENT',doc.id,'DOCUMENT_UPLOADED',null,{sourceType:'PDF'});
        return {...doc,storagePath:undefined,searchText:undefined,documentId:doc.id,jobId:job.id};
      });
    }catch(e){await unlink(storagePath).catch(()=>undefined);throw e;}
  }
  documentsQuery(q:DocumentQueryDto) {
    if(q.from&&q.to&&q.from>q.to) throw new BadRequestException('Начальная дата должна быть не позже конечной');
    const qb=this.db.getRepository(Document).createQueryBuilder('d');
    if(q.deleted==='true') qb.where('d."deletedAt" IS NOT NULL');
    else if(q.deleted!=='all') qb.where('d."deletedAt" IS NULL');
    if(q.q?.trim()) qb.andWhere(`(to_tsvector('russian',d."searchText") @@ websearch_to_tsquery('russian',:q) OR d.title ILIKE :like)`,{q:q.q,like:`%${q.q.replace(/[\\%_]/g,'\\$&')}%`});
    if(q.type) qb.andWhere('d."documentType" = :type',{type:q.type});
    if(q.tag) qb.andWhere(':tag = ANY(d.tags)',{tag:q.tag});
    if(q.status) qb.andWhere('d.status = :status',{status:q.status});
    if(q.from) qb.andWhere('d."documentDate" >= :from',{from:q.from});
    if(q.to) qb.andWhere('d."documentDate" <= :to',{to:q.to});
    return qb;
  }
  async list(q:DocumentQueryDto) {
    const [items,total]=await this.documentsQuery(q).orderBy(`d.${q.sort}`,q.order,'NULLS LAST').addOrderBy('d.id','ASC').skip((q.page-1)*q.pageSize).take(q.pageSize).getManyAndCount();
    return paginate(items,total,q.page,q.pageSize);
  }
  async detail(id:string) {
    const doc=await this.document(id,true);
    const [revision,facts,textRevisions,latestJob,extractionRun]=await Promise.all([
      this.db.getRepository(TextRevision).findOneBy({documentId:id,version:doc.textVersion}),this.facts(id,true),
      this.db.getRepository(TextRevision).find({where:{documentId:id},select:['id','version','createdAt'],order:{version:'DESC'}}),
      this.db.getRepository(ProcessingJob).findOne({where:{documentId:id},order:{createdAt:'DESC'}}),
      this.db.getRepository(ExtractionRun).findOne({where:{documentId:id},order:{createdAt:'DESC'}}),
    ]);
    const rawWarnings=(extractionRun?.rawJson as {warnings?:unknown}|null)?.warnings;
    const processingWarnings=Array.isArray(rawWarnings)?rawWarnings.filter((warning):warning is string=>typeof warning==='string'):[];
    const recipe=(extractionRun?.rawJson as {processingRecipe?:Record<string,unknown>}|null)?.processingRecipe;
    const processingRecipe=recipe?Object.fromEntries(['profile','sourceIRVersion','normalizerVersion','model','modelDigest','generationOptions'].map(k=>[k,recipe[k]])):null;
    const extraction=extractionRun?{id:extractionRun.id,textVersion:extractionRun.textVersion,model:extractionRun.model,modelDigest:extractionRun.modelDigest,promptVersion:extractionRun.promptVersion,schemaVersion:extractionRun.schemaVersion,parserVersion:extractionRun.parserVersion,status:extractionRun.status,validationErrors:extractionRun.validationErrors,createdAt:extractionRun.createdAt,completedAt:extractionRun.completedAt}:null;
    // Never expose a failed, deleted, superseded or earlier-text lab artifact as current.
    const raw=extractionRun?.rawJson as {laboratory?:Laboratory;visit?:Visit;extractionProfile?:string}|null;
    const laboratory=!doc.deletedAt&&doc.status==='READY'&&extractionRun?.status==='READY'&&extractionRun.textVersion===doc.textVersion?raw?.laboratory??null:null;
    const visit=!doc.deletedAt&&doc.status==='READY'&&extractionRun?.status==='READY'&&extractionRun.textVersion===doc.textVersion?raw?.visit??null:null;
    return {...doc,text:revision?.content??'',pages:revision?.pages??[],facts,textRevisions,latestJob,processingWarnings,extraction, laboratory,visit,processingRecipe,extractionProfile:raw?.extractionProfile??'legacy'};
  }
  async revision(id:string,version:number) {
    await this.document(id,true);
    const revision=await this.db.getRepository(TextRevision).findOneBy({documentId:id,version});
    if(!revision) throw new NotFoundException('Версия текста не найдена');
    return revision;
  }
  async update(id:string,dto:UpdateDocumentDto) {
    return this.db.transaction(async m=>{
      const doc=await this.document(id,false,m,true),before={title:doc.title,documentType:doc.documentType,documentDate:doc.documentDate,tags:doc.tags,textVersion:doc.textVersion};
      const {text,tags,...metadata}=dto;
      Object.assign(doc,Object.fromEntries(Object.entries(metadata).filter(([,value])=>value!==undefined)));
      if(tags!==undefined){doc.tags=normalizeTags(tags);await ensureTags(m,doc.tags);}
      if(text!==undefined) {
        doc.textVersion++;
        if(doc.sourceType==='TEXT') doc.sha256=contentHash(text);
        await m.save(TextRevision,m.create(TextRevision,{documentId:id,version:doc.textVersion,content:text,pages:[],parser:'user-edit'}));
        await m.update(MedicalFact,{documentId:id,reviewStatus:'UNREVIEWED'},{active:false});
      }
      const revision=await m.findOneBy(TextRevision,{documentId:id,version:doc.textVersion});
      doc.searchText=`${doc.title}\n${doc.summary}\n${revision?.content??''}`;
      doc.generation++;doc.status=text!==undefined?'UPLOADED':'INDEXING';doc.errorCode=null;
      await m.save(doc);
      const job=await enqueue(m,doc,text!==undefined?'PROCESS':doc.textVersion?'INDEX':'PROCESS');
      await rebuildTimeline(m,doc);
      await audit(m,id,'DOCUMENT',id,text!==undefined?'TEXT_EDITED':'METADATA_UPDATED',before,{...metadata,tags:doc.tags,textVersion:doc.textVersion});
      return {...doc,searchText:undefined,jobId:job.id};
    });
  }
  async remove(id:string) {
    return this.db.transaction(async m=>{
      const doc=await this.document(id,false,m,true);
      doc.deletedAt=new Date();doc.generation++;
      await m.save(doc);
      const job=await enqueue(m,doc,'REMOVE');
      await audit(m,id,'DOCUMENT',id,'DOCUMENT_DELETED');
      return {id,deletedAt:doc.deletedAt,jobId:job.id};
    });
  }
  async restore(id:string) {
    return this.db.transaction(async m=>{
      const doc=await this.document(id,true,m,true);
      if(!doc.deletedAt) throw new ConflictException('Документ уже активен');
      doc.deletedAt=null;doc.generation++;doc.status=doc.textVersion?'INDEXING':'UPLOADED';doc.errorCode=null;
      await m.save(doc);
      const job=await enqueue(m,doc,doc.textVersion?'INDEX':'PROCESS');
      await audit(m,id,'DOCUMENT',id,'DOCUMENT_RESTORED');
      return {...doc,jobId:job.id};
    });
  }
  async reprocess(id:string) {
    return this.db.transaction(async m=>{
      const doc=await this.document(id,false,m,true);
      doc.generation++;doc.status='UPLOADED';doc.errorCode=null;
      await m.save(doc);
      const job=await enqueue(m,doc);
      await audit(m,id,'DOCUMENT',id,'REPROCESS_REQUESTED');
      return {id,documentId:id,jobId:job.id,status:doc.status};
    });
  }
  async original(id:string) {
    await this.document(id);
    const doc=await this.db.getRepository(Document).createQueryBuilder('d').addSelect('d.storagePath').where('d.id = :id',{id}).getOneOrFail();
    if(!doc.storagePath) throw new NotFoundException('У документа нет PDF-оригинала');
    const root=await realpath(resolve(process.env.UPLOAD_DIR??'data/uploads'));
    const path=await realpath(doc.storagePath).catch(()=>{throw new NotFoundException('Оригинал не найден');});
    const rel=relative(root,path);
    if(!rel||rel.startsWith('..')||isAbsolute(rel)) throw new NotFoundException('Оригинал не найден');
    return {path,filename:doc.originalFilename??'document.pdf',mimeType:doc.mimeType==='application/pdf'?'application/pdf':'text/plain; charset=utf-8'};
  }
  async facts(documentId:string,includeDeleted=false) {
    await this.document(documentId,includeDeleted);
    const facts=await this.db.getRepository(MedicalFact).find({where:{documentId,active:true},order:{createdAt:'ASC'}});
    if(!facts.length)return [];
    const sources=await this.db.getRepository(FactProvenance).findBy({factId:In(facts.map(f=>f.id))});
    return facts.map(f=>({...f,provenance:sources.find(p=>p.factId===f.id)??null}));
  }
  async fact(id:string,m:EntityManager=this.db.manager) {
    const f=await m.findOneBy(MedicalFact,{id});
    if(!f)throw new NotFoundException('Факт не найден');
    await this.document(f.documentId,false,m);
    return f;
  }
  async updateFact(id:string,dto:UpdateFactDto) {
    return this.db.transaction(async m=>{
      const f=await this.fact(id,m),doc=await this.document(f.documentId,false,m,true);
      if(!f.active) throw new ConflictException('Факт относится к устаревшей обработке');
      const before=factSnapshot(f);
      Object.assign(f,Object.fromEntries(Object.entries(dto).filter(([,value])=>value!==undefined)));
      if(dto.reviewStatus===undefined) f.reviewStatus='CORRECTED';
      await m.save(f);
      await m.save(FactRevision,m.create(FactRevision,{factId:id,oldValue:before,newValue:factSnapshot(f),changeType:f.reviewStatus}));
      await audit(m,f.documentId,'FACT',id,'FACT_CORRECTED',before,factSnapshot(f));
      doc.generation++;doc.status='INDEXING';doc.errorCode=null;await m.save(doc);
      const job=await enqueue(m,doc,'INDEX');
      await rebuildTimeline(m,doc);
      return {...f,jobId:job.id};
    });
  }
  async factHistory(id:string,q:PaginationDto) {
    await this.fact(id);
    const [items,total]=await this.db.getRepository(FactRevision).findAndCount({where:{factId:id},order:{createdAt:'DESC'},skip:(q.page-1)*q.pageSize,take:q.pageSize});
    return paginate(items,total,q.page,q.pageSize);
  }
  async source(id:string) {
    const f=await this.fact(id),doc=await this.document(f.documentId);
    const source=await this.db.getRepository(FactProvenance).findOneBy({factId:id});
    if(!source) throw new NotFoundException('Источник факта не найден');
    return {...source,documentTitle:doc.title};
  }
  async timeline(q:TimelineQueryDto) {
    const qb=this.db.getRepository(TimelineEvent).createQueryBuilder('t').innerJoin(Document,'d','d.id = t."documentId" AND d."deletedAt" IS NULL');
    if(q.type||q.category) qb.andWhere('t."eventType" = :type',{type:q.type??q.category});
    if(q.documentId) qb.andWhere('t."documentId" = :id',{id:q.documentId});
    if(q.from) qb.andWhere('t."eventDate" >= :from',{from:q.from});
    if(q.to) qb.andWhere('t."eventDate" <= :to',{to:q.to});
    const [items,total]=await qb.orderBy('t.eventDate','DESC','NULLS LAST').addOrderBy('t.id','ASC').skip((q.page-1)*q.pageSize).take(q.pageSize).getManyAndCount();
    const docs=items.length?await this.db.getRepository(Document).findBy({id:In([...new Set(items.map(i=>i.documentId))])}):[];
    return paginate(items.map(i=>({...i,documentTitle:docs.find(d=>d.id===i.documentId)?.title})),total,q.page,q.pageSize);
  }
  async history(q:PaginationDto,documentId?:string) {
    if(documentId) await this.document(documentId,true);
    const [items,total]=await this.db.getRepository(AuditEvent).findAndCount({where:documentId?{documentId}:{},order:{createdAt:'DESC',id:'DESC'},skip:(q.page-1)*q.pageSize,take:q.pageSize});
    return paginate(items,total,q.page,q.pageSize);
  }
  async job(id:string) {
    const job=await this.db.getRepository(ProcessingJob).findOneBy({id});
    if(!job) throw new NotFoundException('Задание не найдено');
    return job;
  }
  async dashboard() {
    const [byType,byStatus,overTime,counts,recentDocuments,recentChanges]=await Promise.all([
      this.db.query(`SELECT "documentType" AS type, count(*)::int AS count FROM documents WHERE "deletedAt" IS NULL GROUP BY "documentType" ORDER BY count DESC`),
      this.db.query(`SELECT status,count(*)::int AS count FROM documents WHERE "deletedAt" IS NULL GROUP BY status`),
      this.db.query(`SELECT to_char("documentDate",'YYYY-MM') AS month,count(*)::int AS count FROM documents WHERE "deletedAt" IS NULL AND "documentDate" IS NOT NULL GROUP BY month ORDER BY month`),
      this.db.query(`SELECT (SELECT count(*)::int FROM medical_facts f JOIN documents d ON d.id=f."documentId" WHERE d."deletedAt" IS NULL AND f.active AND f."reviewStatus" <> 'REJECTED') AS facts,(SELECT count(*)::int FROM timeline_events t JOIN documents d ON d.id=t."documentId" WHERE d."deletedAt" IS NULL) AS events`),
      this.db.getRepository(Document).find({where:{deletedAt:IsNull()},order:{createdAt:'DESC'},take:5}),
      this.db.getRepository(AuditEvent).find({order:{createdAt:'DESC'},take:8}),
    ]);
    const count=(statuses:string[])=>byStatus.filter((v:any)=>statuses.includes(v.status)).reduce((s:number,v:any)=>s+v.count,0);
    return {totalDocuments:byStatus.reduce((s:number,v:any)=>s+v.count,0),processedDocuments:count(['READY']),failedDocuments:count(['FAILED','UNSUPPORTED_OCR_REQUIRED']),pendingDocuments:count(['UPLOADED','PARSING','EXTRACTING','INDEXING']),medicalFacts:counts[0].facts,timelineEvents:counts[0].events,documentsByType:byType,documentsOverTime:overTime,recentDocuments,recentChanges};
  }
  async tags(){return this.db.getRepository(Tag).find({order:{name:'ASC'}});}
  async createTag(name:string){return this.db.getRepository(Tag).save({name:name.trim()});}
  async editTag(id:string,name:string) {
    return this.db.transaction(async m=>{
      const tag=await m.findOneBy(Tag,{id});if(!tag)throw new NotFoundException('Тег не найден');
      const old=tag.name;tag.name=name.trim();await m.save(tag);
      await m.query(`UPDATE documents SET tags=array_replace(tags,$1,$2),"updatedAt"=now() WHERE $1=ANY(tags)`,[old,tag.name]);
      await audit(m,null,'TAG',id,'TAG_RENAMED',{name:old},{name:tag.name});return tag;
    });
  }
  async deleteTag(id:string) {
    return this.db.transaction(async m=>{
      const tag=await m.findOneBy(Tag,{id});if(!tag)throw new NotFoundException('Тег не найден');
      await m.query(`UPDATE documents SET tags=array_remove(tags,$1),"updatedAt"=now() WHERE $1=ANY(tags)`,[tag.name]);
      await m.delete(Tag,id);await audit(m,null,'TAG',id,'TAG_DELETED',{name:tag.name});return {ok:true};
    });
  }
  async ask(question:string,documentIds?:string[],dateFrom?:string,dateTo?:string) {
    if(dateFrom&&dateTo&&dateFrom>dateTo)throw new BadRequestException({code:'INVALID_PERIOD',message:'Начало периода должно быть не позже конца'});
    const qb=this.db.getRepository(Document).createQueryBuilder('d').select(['d.id','d.generation','d.textVersion','d.documentDate']).where('d."deletedAt" IS NULL AND d.status = :status',{status:'READY'});
    if(documentIds!==undefined){if(!documentIds.length)return {answer:'В выбранном контексте нет доступных документов.',sources:[],insufficientContext:true};qb.andWhere('d.id IN (:...ids)',{ids:documentIds});}
    const snapshots=await qb.getMany();
    const allowed=snapshots.map(d=>d.id);
    if(!allowed.length) return {answer:'В архиве пока нет готовых документов для ответа.',sources:[],insufficientContext:true};
    const result=await this.ai.call('ask',{question,documentIds:allowed,documents:snapshots.map(d=>({documentId:d.id,documentDate:d.documentDate})),dateFrom,dateTo});
    const current=await this.db.getRepository(Document).find({where:{id:In(allowed),deletedAt:IsNull(),status:'READY'},select:['id','generation','textVersion']});
    const stillAllowed=new Set(current.filter(d=>snapshots.some(s=>s.id===d.id&&s.generation===d.generation&&s.textVersion===d.textVersion)).map(d=>d.id));
    // Never return an answer derived from a document deleted/edited while generation was running.
    if((result.sources??[]).some((s:any)=>!stillAllowed.has(s.documentId))) return {answer:'Состав архива изменился во время ответа. Повторите вопрос.',sources:[],insufficientContext:true};
    return {...result,sources:(result.sources??[]).map((s:any)=>({...s,textVersion:snapshots.find(d=>d.id===s.documentId)?.textVersion,generation:snapshots.find(d=>d.id===s.documentId)?.generation}))};
  }
}
