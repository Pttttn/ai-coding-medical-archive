import 'reflect-metadata';
import {irHash,SourceIR} from '../src/source-ir';
import {Test} from '@nestjs/testing';
import {INestApplication,ValidationPipe} from '@nestjs/common';
import request from 'supertest';
import {DataSource} from 'typeorm';
import {randomUUID} from 'node:crypto';
import {mkdtemp,readFile,rm} from 'node:fs/promises';
import {tmpdir} from 'node:os';
import {join,resolve} from 'node:path';
import {AppModule} from '../src/app.module';
import {AiClient,AiError,contentHash} from '../src/core';
import {createDataSource} from '../src/database';
import {ProcessingService} from '../src/processing.service';
import {SafeErrorFilter} from '../src/error.filter';
import {Document,ProcessingJob,Consultation,ExtractionRun} from '../src/entities';
import {SeedService} from '../src/seed.service';

const suite=process.env.TEST_DATABASE_URL?describe:describe.skip;
suite('PostgreSQL migration and REST integration (local AI double)',()=>{
  let db:DataSource,app:INestApplication,worker:ProcessingService,uploads:string;
  const ai={call:jest.fn()};
  const mock=async(route:string,body:any):Promise<any>=>{
    if(route==='process'){
      const text=body.text??'LDL 4.7 mmol/L.';
      return {text,pages:[{pageNumber:null,text}],extraction:{documentType:'LAB_REPORT',documentDate:null,summary:'Local extraction',tags:['lipid'],facts:[{type:'LAB_RESULT',name:'LDL',valueText:null,valueNumber:4.7,unit:'mmol/L',eventDate:null,assertionStatus:'CONFIRMED',confidence:0.8,provenance:{page:null,sourceText:text}}]},model:'unit-double',promptVersion:'1',schemaVersion:'1',parserVersion:'1'};
    }
    if(route==='ask')return {answer:'LDL 4.7 mmol/L.',sources:body.documentIds.map((id:string)=>({documentId:id,source:id,chunkId:'test-chunk',position:0,text:'LDL 4.7 mmol/L.'})),insufficientContext:false};
    if(route==='consultation')return {content:'# Consultation\nNo fever. LDL 4.7 mmol/L. Dose 20 mg.',warnings:[]};
    return {ok:true};
  };
  const note=async(text='LDL 4.7 mmol/L.')=>(await request(app.getHttpServer()).post('/api/documents/note').send({title:'Лабораторная заметка',text,tags:['lipid']}).expect(201)).body;
  const ready=async(text?:string)=>{const d=await note(text);await worker.tick();return (await request(app.getHttpServer()).get('/api/documents/'+d.id).expect(200)).body;};
  it('passes document dates and explicit period to archive AI and rejects inverted periods',async()=>{
    const d=await ready();
    await db.getRepository(Document).update(d.id,{documentDate:'2026-01-15'});
    ai.call.mockClear();
    await request(app.getHttpServer()).post('/api/ask').send({question:'Какие отклонения?',dateFrom:'2025-09-24',dateTo:'2026-09-24'}).expect(201);
    expect(ai.call).toHaveBeenCalledWith('ask',expect.objectContaining({dateFrom:'2025-09-24',dateTo:'2026-09-24',documents:[{documentId:d.id,documentDate:'2026-01-15'}]}));
    ai.call.mockClear();
    await request(app.getHttpServer()).post('/api/ask').send({question:'Какие отклонения?',dateFrom:'2026-09-24',dateTo:'2025-09-24'}).expect(400);
    expect(ai.call).not.toHaveBeenCalled();
  });
  beforeAll(async()=>{
    const url=process.env.TEST_DATABASE_URL!;
    if(!new URL(url).pathname.includes('test'))throw new Error('Integration tests require a dedicated test database');
    process.env.SEED_ENABLED='false';process.env.WORKER_ENABLED='false';
    uploads=await mkdtemp(join(tmpdir(),'archive-backend-test-'));process.env.UPLOAD_DIR=uploads;
    db=createDataSource(url);await db.initialize();
    const module=await Test.createTestingModule({imports:[AppModule]}).overrideProvider(DataSource).useValue(db).overrideProvider(AiClient).useValue(ai).compile();
    app=module.createNestApplication();app.setGlobalPrefix('api');app.useGlobalPipes(new ValidationPipe({transform:true,whitelist:true,forbidNonWhitelisted:true}));app.useGlobalFilters(new SafeErrorFilter());await app.init();
    worker=app.get(ProcessingService);
  },30000);
  beforeEach(async()=>{
    await db.query('TRUNCATE documents, tags, consultations CASCADE');
    ai.call.mockReset();ai.call.mockImplementation(mock);
  });
  afterAll(async()=>{if(app)await app.close();if(db?.isInitialized)await db.destroy();if(uploads)await rm(uploads,{recursive:true,force:true});});
  const withIR=async(route:string,body:any)=>{
    const result=await mock(route,body);
    if(route!=='process')return result;
    const text=result.pages[0].text,length=Buffer.byteLength(text);
    const span={pageIndex:0,startByte:0,endByte:length};
    const content={schemaVersion:'source-ir-v1',stage:'SOURCE_ONLY',documentId:body.documentId,parserVersion:'synthetic-test',normalizerVersion:'whitespace-map-v1',sourceHash:irHash(result.pages),pages:result.pages,blocks:[{blockId:'p0:b0',kind:'paragraph',source:span,normalizedText:text,mapping:[{normalizedStartByte:0,normalizedEndByte:length,source:span,operation:'IDENTITY'}]}]};
    return {...result,sourceIR:{...content,irHash:irHash(content)} as SourceIR};
  };
  const visitMock=async(route:string,body:any,reviewed=false)=>{
    if(route!=='process')return mock(route,body);
    const f=JSON.parse(await readFile(join(__dirname,reviewed?'../../contracts/visit-assertions-v2.synthetic.json':'../../contracts/visit-assertions-v1.synthetic.json'),'utf8'));
    f.sourceIR.documentId=body.documentId;
    const {irHash:old,...irBody}=f.sourceIR;void old;f.sourceIR.irHash=irHash(irBody);
    f.visit.sourceIRHash=f.sourceIR.irHash;
    const {artifactHash:previous,...visitBody}=f.visit;void previous;f.visit.artifactHash=irHash(visitBody);
    return {...f,text:f.sourceIR.pages[0].text,pages:f.sourceIR.pages,extractionProfile:'clinical-v1',model:'unit-double'};
  };
  it('persists visit annotation, keeps review separate and hides stale results',async()=>{
    ai.call.mockImplementation(visitMock);const d=await ready();
    expect(d.visit.statements).toHaveLength(7);
    const medication=d.facts.find((f:any)=>f.name==='Аторвастатин');
    expect(medication.assertionStatus).toBe('UNKNOWN');
    await request(app.getHttpServer()).patch('/api/facts/'+medication.id).send({valueText:'Synthetic user correction',reviewStatus:'CORRECTED'}).expect(200);
    await worker.tick();
    await request(app.getHttpServer()).post('/api/documents/'+d.id+'/reprocess').expect(201);
    expect((await request(app.getHttpServer()).get('/api/documents/'+d.id)).body.visit).toBeNull();
    await worker.tick();
    const repeated=(await request(app.getHttpServer()).get('/api/documents/'+d.id)).body;
    expect(repeated.facts.find((f:any)=>f.name==='Аторвастатин').valueText).toBe('Synthetic user correction');
    expect(repeated.visit.statements[5].medicationState).toBe('NOT_STARTED');
    expect(repeated.facts).toHaveLength(7);
    await request(app.getHttpServer()).patch('/api/documents/'+d.id).send({text:'Synthetic updated source.'}).expect(200);
    expect((await request(app.getHttpServer()).get('/api/documents/'+d.id)).body.visit).toBeNull();
    await request(app.getHttpServer()).delete('/api/documents/'+d.id).expect(200);
    expect((await request(app.getHttpServer()).get('/api/documents/'+d.id)).body.visit).toBeNull();
  });
  it('fails a visit projection that promotes family history before publishing facts',async()=>{
    ai.call.mockImplementation(async(route,body)=>{const r=await visitMock(route,body);if(route==='process')r.extraction.facts[1].assertionStatus='CONFIRMED';return r;});
    const d=await ready();expect(d.status).toBe('FAILED');expect(d.errorCode).toBe('VISIT_ARTIFACT_INVALID');
    expect(d.facts).toHaveLength(0);expect(d.visit).toBeNull();
  });
  it('publishes source review disagreements as UNKNOWN and preserves user correction',async()=>{
    ai.call.mockImplementation((route,body)=>visitMock(route,body,true));const d=await ready();
    expect(d.visit.schemaVersion).toBe('visit-assertions-v2');
    const disputed=d.facts.find((f:any)=>f.name==='Аторвастатин');
    expect(disputed).toMatchObject({type:'OBSERVATION',assertionStatus:'UNKNOWN'});
    await request(app.getHttpServer()).patch('/api/facts/'+disputed.id).send({valueText:'Synthetic reviewed correction',reviewStatus:'CORRECTED'}).expect(200);
    await worker.tick();
    await request(app.getHttpServer()).post('/api/documents/'+d.id+'/reprocess').expect(201);
    expect((await request(app.getHttpServer()).get('/api/documents/'+d.id)).body.visit).toBeNull();
    await worker.tick();
    const current=(await request(app.getHttpServer()).get('/api/documents/'+d.id)).body;
    expect(current.facts.find((f:any)=>f.name==='Аторвастатин').valueText).toBe('Synthetic reviewed correction');
    expect(current.visit.verifications[5].status).toBe('DISAGREES');
    expect(current.visit.statements[5].medicationState).toBe('TAKING');
  });
  it('does not publish a claimed agreement with a contradictory alternative',async()=>{
    ai.call.mockImplementation(async(route,body)=>{const r=await visitMock(route,body,true);if(route==='process'){
      r.visit.verifications[5].status='AGREES';
      const {artifactHash,...rest}=r.visit;void artifactHash;r.visit.artifactHash=irHash(rest);
    }return r;});
    const d=await ready();expect(d.status).toBe('FAILED');expect(d.facts).toHaveLength(0);expect(d.visit).toBeNull();
  });
  const labMock=async(route:string,body:any)=>{
    if(route!=='process')return mock(route,body);
    const fixture=JSON.parse(await readFile(join(__dirname,'../../contracts/lab-rows-v1.synthetic.json'),'utf8'));
    const sourceIR=fixture.sourceIR;sourceIR.documentId=body.documentId;
    const {irHash:old,...irBody}=sourceIR;void old;sourceIR.irHash=irHash(irBody);
    const laboratory=fixture.laboratory;laboratory.sourceIRHash=sourceIR.irHash;
    const {artifactHash:previous,...labBody}=laboratory;void previous;laboratory.artifactHash=irHash(labBody);
    return {text:sourceIR.pages[0].text,pages:sourceIR.pages,sourceIR,laboratory,extractionProfile:'lab-rows-v1',
      extraction:{documentType:'LAB_REPORT',documentDate:'2026-06-18',summary:'Synthetic lab',tags:[],facts:fixture.facts},
      model:'deterministic:lab-rows-v1',promptVersion:'lab-rows-v1',schemaVersion:'medical-facts-v1'};
  };
  it('persists typed lab annotation, preserves reviewed overlay and hides artifact during pending/edit/delete',async()=>{
    ai.call.mockImplementation(labMock);const d=await ready();
    expect(d.laboratory.rows).toHaveLength(2);expect(d.facts[0].type).toBe('LAB_RESULT');
    const scalar=d.facts.find((f:any)=>f.name==='MCV');
    await request(app.getHttpServer()).patch('/api/facts/'+scalar.id).send({valueNumber:75,reviewStatus:'CORRECTED'}).expect(200);
    await worker.tick();
    await request(app.getHttpServer()).post('/api/documents/'+d.id+'/reprocess').expect(201);
    expect((await request(app.getHttpServer()).get('/api/documents/'+d.id)).body.laboratory).toBeNull();
    await worker.tick();
    const repeated=(await request(app.getHttpServer()).get('/api/documents/'+d.id)).body;
    expect(repeated.facts.find((f:any)=>f.name==='MCV').valueNumber).toBe(75);
    expect(repeated.laboratory.rows[1].result.numericValue).toBe('74.20');
    expect(repeated.facts).toHaveLength(2);
    await request(app.getHttpServer()).patch('/api/documents/'+d.id).send({text:'Updated source text, no longer the same lab.'}).expect(200);
    expect((await request(app.getHttpServer()).get('/api/documents/'+d.id)).body.laboratory).toBeNull();
    await request(app.getHttpServer()).delete('/api/documents/'+d.id).expect(200);
    expect((await request(app.getHttpServer()).get('/api/documents/'+d.id)).body.laboratory).toBeNull();
  });
  it('fails inconsistent lab projection before publishing facts or annotation',async()=>{
    ai.call.mockImplementation(async(route,body)=>{const r=await labMock(route,body);if(route==='process')r.extraction.facts[0].valueNumber=5;return r;});
    const d=await ready();expect(d.status).toBe('FAILED');expect(d.errorCode).toBe('LAB_ARTIFACT_INVALID');
    expect(d.facts).toHaveLength(0);expect(d.laboratory).toBeNull();
  });
  it('stores immutable source IR and reuses identical revision after reprocessing',async()=>{
    ai.call.mockImplementation(withIR);
    const d=await ready();
    const ir=(await request(app.getHttpServer()).get('/api/documents/'+d.id+'/source-ir').expect(200)).body;
    expect(ir.content.pages[0].text).toBe(d.text);
    await request(app.getHttpServer()).post('/api/documents/'+d.id+'/reprocess').expect(201);
    await worker.tick();
    expect((await db.query('SELECT id FROM source_ir_revisions WHERE "documentId"=$1',[d.id]))).toHaveLength(1);
    await expect(db.query('UPDATE source_ir_revisions SET content=$1 WHERE id=$2',[{},ir.id])).rejects.toThrow('immutable');
    await request(app.getHttpServer()).delete('/api/documents/'+d.id).expect(200);
    await request(app.getHttpServer()).get('/api/documents/'+d.id+'/source-ir').expect(404);
  });
  it('creates a new source revision when page attribution changes but text does not',async()=>{
    ai.call.mockImplementation(withIR);const d=await ready();
    const first=(await request(app.getHttpServer()).get('/api/documents/'+d.id+'/source-ir').expect(200)).body;
    ai.call.mockImplementation(async(route,body)=>{const r=await withIR(route,body);if(route==='process'){
      r.pages[0].pageNumber=1;r.sourceIR.sourceHash=irHash(r.pages);
      const {irHash:old,...content}=r.sourceIR;void old;r.sourceIR.irHash=irHash(content);
    }return r;});
    await request(app.getHttpServer()).post('/api/documents/'+d.id+'/reprocess').expect(201);await worker.tick();
    const after=(await request(app.getHttpServer()).get('/api/documents/'+d.id).expect(200)).body;
    expect(after.text).toBe(d.text);expect(after.textVersion).toBe(d.textVersion+1);
    const second=(await request(app.getHttpServer()).get('/api/documents/'+d.id+'/source-ir').expect(200)).body;
    expect(second.textRevisionId).not.toBe(first.textRevisionId);
    const old=await db.query('SELECT content FROM source_ir_revisions WHERE id=$1',[first.id]);
    expect(old[0].content.pages[0].pageNumber).toBeNull();
  });
  it('rejects corrupted IR before persisting new facts or IR',async()=>{
    ai.call.mockImplementation(async(route,body)=>{const r=await withIR(route,body);if(route==='process')r.sourceIR.blocks[0].normalizedText='invented';return r;});
    const d=await ready();
    expect(d.status).toBe('FAILED');expect(d.errorCode).toBe('SOURCE_IR_INVALID');expect(d.facts).toHaveLength(0);
    expect(await db.query('SELECT id FROM source_ir_revisions WHERE "documentId"=$1',[d.id])).toHaveLength(0);
  });
  it('migrates existing source text without rewriting it',async()=>{
    await db.undoLastMigration();
    await db.undoLastMigration();
    const d=await note();
    await db.runMigrations();
    ai.call.mockImplementation(withIR);await worker.tick();
    const after=(await request(app.getHttpServer()).get('/api/documents/'+d.id).expect(200)).body;
    expect(after.text).toBe('LDL 4.7 mmol/L.');expect(after.textVersion).toBe(1);
    await request(app.getHttpServer()).get('/api/documents/'+d.id+'/source-ir').expect(200);
  });
  it('migrates actual PostgreSQL and responds with readiness',async()=>{await request(app.getHttpServer()).get('/api/health').expect(200);const migrations=await db.query('SELECT * FROM migrations');expect(migrations).toHaveLength(3);});
  it('validates unknown properties and empty title at the API boundary',async()=>{await request(app.getHttpServer()).post('/api/documents/note').send({title:' ',text:'ok text',storagePath:'/secret'}).expect(400);});
  it('returns durable IDs before inference and completes the worker job',async()=>{const d=await note();expect(d.jobId).toBeDefined();expect(ai.call).not.toHaveBeenCalled();await worker.tick();const job=await db.getRepository(ProcessingJob).findOneByOrFail({id:d.jobId});expect(job.status).toBe('READY');expect((await db.getRepository(Document).findOneByOrFail({id:d.id})).status).toBe('READY');});
  it('detects duplicate text documents with safe conflict error',async()=>{await note();const r=await request(app.getHttpServer()).post('/api/documents/note').send({title:'Second',text:'LDL 4.7 mmol/L.'}).expect(409);expect(r.body.code).toBe('DUPLICATE');expect(r.body).not.toHaveProperty('query');});
  it('searches PostgreSQL text and filters with server pagination',async()=>{await ready();await note('Другая заметка о симптомах.');const r=await request(app.getHttpServer()).get('/api/documents?page=1&pageSize=1&tag=lipid&q=LDL').expect(200);expect(r.body.total).toBe(1);expect(r.body.items).toHaveLength(1);});
  it('creates actual provenance and leaves unknown medical dates null',async()=>{const d=await ready();expect(d.documentDate).toBeNull();expect(d.facts).toHaveLength(1);const r=await request(app.getHttpServer()).get('/api/facts/'+d.facts[0].id+'/source').expect(200);expect(r.body.textVersion).toBe(1);expect(r.body.pageNumber).toBeNull();expect(r.body.sourceText).toBe('LDL 4.7 mmol/L.');});
  it('preserves corrected fact value and original provenance after reprocessing',async()=>{const d=await ready(),f=d.facts[0];await request(app.getHttpServer()).patch('/api/facts/'+f.id).send({valueNumber:4.1}).expect(200);await request(app.getHttpServer()).post('/api/documents/'+d.id+'/reprocess').expect(201);await worker.tick();await worker.tick();const updated=(await request(app.getHttpServer()).get('/api/documents/'+d.id).expect(200)).body;expect(updated.facts).toHaveLength(1);expect(updated.facts[0].valueNumber).toBe(4.1);expect(updated.facts[0].originalValue.valueNumber).toBe(4.7);const h=await request(app.getHttpServer()).get('/api/facts/'+f.id+'/history').expect(200);expect(h.body.total).toBe(1);expect(h.body.items[0].oldValue.valueNumber).toBe(4.7);});
  it('stores an edited value as a user correction even when CONFIRMED is requested',async()=>{
    const d=await ready(),f=d.facts[0];
    const confirmed=(await request(app.getHttpServer()).patch('/api/facts/'+f.id).send({valueNumber:5.2,reviewStatus:'CONFIRMED'}).expect(200)).body;
    expect(confirmed.reviewStatus).toBe('CORRECTED');
    // Unchanged value may still be confirmed; the extracted value stays the source claim.
    await worker.tick();
    const g=(await ready('HDL 1.2 mmol/L.')).facts[0];
    expect((await request(app.getHttpServer()).patch('/api/facts/'+g.id).send({valueNumber:4.7,reviewStatus:'CONFIRMED'}).expect(200)).body.reviewStatus).toBe('CONFIRMED');
    // An UNREVIEWED edit is also a correction, so reprocessing cannot silently discard it.
    await worker.tick();
    const h=(await ready('LDL 3.9 mmol/L.')).facts[0];
    expect((await request(app.getHttpServer()).patch('/api/facts/'+h.id).send({unit:'mg/dL',reviewStatus:'UNREVIEWED'}).expect(200)).body.reviewStatus).toBe('CORRECTED');
    // Confirming a previously corrected value does not turn it into a document claim.
    expect((await request(app.getHttpServer()).patch('/api/facts/'+f.id).send({reviewStatus:'CONFIRMED'}).expect(200)).body.reviewStatus).toBe('CORRECTED');
    const history=(await request(app.getHttpServer()).get('/api/facts/'+f.id+'/history').expect(200)).body;
    expect(history.items.map((i:any)=>i.changeType)).toEqual(['CORRECTED','CORRECTED']);
  });
  it('keeps fact extraction when metadata is edited before a pending text edit is processed',async()=>{
    const d=await ready();
    await request(app.getHttpServer()).patch('/api/documents/'+d.id).send({text:'LDL 4.1 mmol/L.'}).expect(200);
    await request(app.getHttpServer()).patch('/api/documents/'+d.id).send({title:'Переименованный анализ'}).expect(200);
    for(let n=0;n<4;n++)await worker.tick();
    const updated=(await request(app.getHttpServer()).get('/api/documents/'+d.id).expect(200)).body;
    expect(updated.status).toBe('READY');
    expect(updated.textVersion).toBe(2);
    expect(updated.extraction.textVersion).toBe(2);
    expect(updated.facts).toHaveLength(1);
    expect(updated.facts[0].provenance.sourceText).toBe('LDL 4.1 mmol/L.');
  });
  it('does not turn a failed extraction READY after a metadata edit',async()=>{
    const d=await note();
    ai.call.mockRejectedValueOnce(new AiError('EXTRACTION_INVALID'));
    await worker.tick();
    expect((await db.getRepository(Document).findOneByOrFail({id:d.id})).status).toBe('FAILED');
    ai.call.mockRejectedValueOnce(new AiError('EXTRACTION_INVALID'));
    const edited=(await request(app.getHttpServer()).patch('/api/documents/'+d.id).send({title:'Новое название'}).expect(200)).body;
    expect((await db.getRepository(ProcessingJob).findOneByOrFail({id:edited.jobId})).operation).toBe('PROCESS');
    await worker.tick();
    expect((await db.getRepository(Document).findOneByOrFail({id:d.id})).status).toBe('FAILED');
  });
  it('re-extracts a pending text edit when a reviewed fact is corrected before processing',async()=>{
    const d=await ready(),f=d.facts[0];
    await request(app.getHttpServer()).patch('/api/facts/'+f.id).send({reviewStatus:'CONFIRMED'}).expect(200);
    await worker.tick();
    await request(app.getHttpServer()).patch('/api/documents/'+d.id).send({text:'LDL 4.7 mmol/L.\nHDL 1.2 mmol/L.'}).expect(200);
    const corrected=(await request(app.getHttpServer()).patch('/api/facts/'+f.id).send({valueNumber:4.8}).expect(200)).body;
    expect((await db.getRepository(ProcessingJob).findOneByOrFail({id:corrected.jobId})).operation).toBe('PROCESS');
    for(let n=0;n<4;n++)await worker.tick();
    const updated=(await request(app.getHttpServer()).get('/api/documents/'+d.id).expect(200)).body;
    expect(updated.status).toBe('READY');
    expect(updated.extraction.textVersion).toBe(2);
    expect(updated.facts.find((x:any)=>x.id===f.id).valueNumber).toBe(4.8);
  });
  it('keeps immutable prior text and excludes pending edits from RAG',async()=>{const d=await ready();await request(app.getHttpServer()).patch('/api/documents/'+d.id).send({text:'LDL 4.1 mmol/L.'}).expect(200);const rev=await request(app.getHttpServer()).get('/api/documents/'+d.id+'/text-revisions/1').expect(200);expect(rev.body.content).toBe('LDL 4.7 mmol/L.');ai.call.mockClear();const answer=await request(app.getHttpServer()).post('/api/ask').send({question:'Каков LDL?'}).expect(201);expect(answer.body.insufficientContext).toBe(true);expect(ai.call).not.toHaveBeenCalled();});
  it('soft deletes from active archive, facts, timeline and dashboard, then removes index',async()=>{const d=await ready();await request(app.getHttpServer()).delete('/api/documents/'+d.id).expect(200);expect((await request(app.getHttpServer()).get('/api/documents').expect(200)).body.total).toBe(0);expect((await request(app.getHttpServer()).get('/api/timeline').expect(200)).body.total).toBe(0);expect((await request(app.getHttpServer()).get('/api/dashboard').expect(200)).body.medicalFacts).toBe(0);await request(app.getHttpServer()).get('/api/facts/'+d.facts[0].id+'/source').expect(404);await worker.tick();expect(ai.call).toHaveBeenCalledWith('remove',{documentId:d.id});});
  it('restores trash and reindexes without overwriting source history',async()=>{const d=await ready();await request(app.getHttpServer()).delete('/api/documents/'+d.id).expect(200);await worker.tick();expect((await request(app.getHttpServer()).get('/api/documents?deleted=true').expect(200)).body.total).toBe(1);await request(app.getHttpServer()).post('/api/documents/'+d.id+'/restore').expect(201);await worker.tick();const r=await request(app.getHttpServer()).get('/api/documents/'+d.id).expect(200);expect(r.body.status).toBe('READY');expect(r.body.textRevisions).toHaveLength(1);});
  it('renames and deletes tags across document associations',async()=>{await ready();const tags=(await request(app.getHttpServer()).get('/api/tags').expect(200)).body;const id=tags.find((t:any)=>t.name==='lipid').id;await request(app.getHttpServer()).patch('/api/tags/'+id).send({name:'липиды'}).expect(200);expect((await request(app.getHttpServer()).get('/api/documents?tag='+encodeURIComponent('липиды')).expect(200)).body.total).toBe(1);await request(app.getHttpServer()).delete('/api/tags/'+id).expect(200);expect((await request(app.getHttpServer()).get('/api/documents?tag='+encodeURIComponent('липиды')).expect(200)).body.total).toBe(0);});
  it('rejects fake PDF and stores controlled original path for valid signature',async()=>{await request(app.getHttpServer()).post('/api/documents/upload').field('title','fake').attach('file',Buffer.from('bad'),{filename:'fake.pdf',contentType:'application/pdf'}).expect(400);const r=await request(app.getHttpServer()).post('/api/documents/upload').field('title','PDF').attach('file',Buffer.from('%PDF-1.7\nsynthetic'),{filename:'demo.pdf',contentType:'application/pdf'}).expect(201);expect(r.body.storagePath).toBeUndefined();const original=await request(app.getHttpServer()).get('/api/documents/'+r.body.id+'/original').expect(200);expect(original.headers['content-type']).toContain('application/pdf');});
  it('handles OCR-required documents with safe persisted errors',async()=>{const d=await note();ai.call.mockRejectedValue(new AiError('UNSUPPORTED_OCR_REQUIRED'));await worker.tick();expect((await db.getRepository(Document).findOneByOrFail({id:d.id})).status).toBe('UNSUPPORTED_OCR_REQUIRED');expect((await db.getRepository(ProcessingJob).findOneByOrFail({id:d.jobId})).errorCode).toBe('UNSUPPORTED_OCR_REQUIRED');});
  it('shows partial parsing warnings and safe extraction metadata without raw AI content',async()=>{ai.call.mockImplementation(async(route,body)=>{const r=await mock(route,body);return route==='process'?{...r,warnings:['Page 2 has no text layer',42,{unexpected:'data'}]}:r;});const d=await ready();expect(d.processingWarnings).toEqual(['Page 2 has no text layer']);expect(d.extraction.model).toBe('unit-double');expect(d.extraction.textVersion).toBe(1);expect(d.extraction).not.toHaveProperty('rawJson');});
  it('records extraction versions and safe raw structured output locally',async()=>{const d=await ready();const run=await db.getRepository(ExtractionRun).findOneByOrFail({documentId:d.id});expect(run.model).toBe('unit-double');expect(run.status).toBe('READY');expect(run.textVersion).toBe(1);});
  it('lists saved drafts without raw contexts and keeps pagination stable',async()=>{
    const d=await ready();
    const c=(await request(app.getHttpServer()).post('/api/consultations/prepare').send({question:'Saved consultation example',documentIds:[d.id]}).expect(201)).body;
    const list=(await request(app.getHttpServer()).get('/api/consultations?q=Saved&pageSize=1').expect(200)).body;
    expect(list.total).toBe(1);expect(list.items[0]).toMatchObject({id:c.id,responseCount:0,sourceCount:1});
    expect(list.items[0].contexts).toBeUndefined();expect(list.items[0].content).toBeUndefined();
    expect((await request(app.getHttpServer()).get('/api/consultations/'+c.id).expect(200)).body.content).toBe(c.content);
    await request(app.getHttpServer()).get('/api/consultations?page=0').expect(400);
  });
  it('binds idempotent responses to immutable reviewed versions after later edits',async()=>{
    const d=await ready();
    const c=(await request(app.getHttpServer()).post('/api/consultations/prepare').send({question:'Review archived request',documentIds:[d.id]}).expect(201)).body;
    const path='/api/consultations/'+c.id;
    await request(app.getHttpServer()).post(path+'/responses').send({id:randomUUID(),promptId:randomUUID(),model:'Synthetic test model',content:'Synthetic response'}).expect(400);
    await request(app.getHttpServer()).post(path+'/review').send({contentHash:c.contentHash}).expect(201);
    await request(app.getHttpServer()).post(path+'/review').send({contentHash:c.contentHash}).expect(201);
    const first=(await request(app.getHttpServer()).get(path).expect(200)).body;
    expect(first.prompts).toHaveLength(1);
    await request(app.getHttpServer()).patch(path).send({content:c.content+' Changed draft.'}).expect(200);
    const payload={id:randomUUID(),promptId:first.prompts[0].id,model:'Synthetic test model',content:'<script>untrusted</script> Not a diagnosis.'};
    await request(app.getHttpServer()).post(path+'/responses').send(payload).expect(201);
    await request(app.getHttpServer()).post(path+'/responses').send(payload).expect(201);
    await request(app.getHttpServer()).post(path+'/responses').send({...payload,content:'Changed response'}).expect(409);
    const after=(await request(app.getHttpServer()).get(path).expect(200)).body;
    expect(after.responses).toHaveLength(1);expect(after.responses[0].content).toBe(payload.content);
    expect(after.prompts[0].content).toBe(c.content);expect(after.reviewedHash).toBeNull();
    expect((await request(app.getHttpServer()).get('/api/documents/'+d.id).expect(200)).body.facts).toHaveLength(d.facts.length);
    await expect(db.query('UPDATE consultation_prompts SET content=$1 WHERE id=$2',['tampered',payload.promptId])).rejects.toThrow();
    await expect(db.query('UPDATE consultation_responses SET content=$1 WHERE id=$2',['tampered',payload.id])).rejects.toThrow();
    const other=(await request(app.getHttpServer()).post('/api/consultations/prepare').send({question:'Other request',documentIds:[d.id]}).expect(201)).body;
    await request(app.getHttpServer()).post('/api/consultations/'+other.id+'/responses').send({...payload,id:randomUUID()}).expect(400);
    await request(app.getHttpServer()).post(path+'/responses').send({...payload,id:randomUUID(),model:' '}).expect(400);
    expect((await request(app.getHttpServer()).get('/api/consultations?q=Review').expect(200)).body.items[0].responseCount).toBe(1);
  });
  it('upgrades existing reviewed consultations without losing drafts',async()=>{
    await db.undoLastMigration();
    const reviewed=await db.getRepository(Consultation).save({question:'Legacy reviewed',content:'Exact legacy text',contentHash:contentHash('Exact legacy text'),reviewedHash:contentHash('Exact legacy text'),status:'REVIEWED',warnings:[],sourceRefs:[],contexts:[]});
    const draft=await db.getRepository(Consultation).save({question:'Legacy draft',content:'Draft text',contentHash:contentHash('Draft text'),reviewedHash:null,warnings:[],sourceRefs:[],contexts:[]});
    await db.runMigrations();
    const after=(await request(app.getHttpServer()).get('/api/consultations/'+reviewed.id).expect(200)).body;
    expect(after.prompts).toHaveLength(1);expect(after.prompts[0].content).toBe('Exact legacy text');
    expect((await request(app.getHttpServer()).get('/api/consultations/'+draft.id).expect(200)).body.prompts).toHaveLength(0);
  });
  it('blocks consultation export until exact review and invalidates it after edit',async()=>{const d=await ready();const c=(await request(app.getHttpServer()).post('/api/consultations/prepare').send({question:'Prepare LDL context',documentIds:[d.id]}).expect(201)).body;await request(app.getHttpServer()).get('/api/consultations/'+c.id+'/export').expect(409);await request(app.getHttpServer()).post('/api/consultations/'+c.id+'/review').send({contentHash:contentHash('wrong')}).expect(409);await request(app.getHttpServer()).post('/api/consultations/'+c.id+'/review').send({contentHash:c.contentHash}).expect(201);expect((await request(app.getHttpServer()).get('/api/consultations/'+c.id+'/export').expect(200)).text).toBe(c.content);await request(app.getHttpServer()).patch('/api/consultations/'+c.id).send({content:c.content+'\nReviewed edit'}).expect(200);await request(app.getHttpServer()).get('/api/consultations/'+c.id+'/export').expect(409);});
  it('prepares explicitly selected sources even when QA abstains and preserves corrections',async()=>{
    const d=await ready();
    await request(app.getHttpServer()).patch('/api/facts/'+d.facts[0].id).send({valueNumber:4.1,reviewStatus:'CORRECTED'}).expect(200);
    await worker.tick();ai.call.mockClear();
    ai.call.mockImplementation(async(route,body)=>route==='ask'?{answer:'Insufficient',sources:[],insufficientContext:true}:mock(route,body));
    const r=await request(app.getHttpServer()).post('/api/consultations/prepare').send({question:'Prepare the selected record',documentIds:[d.id]}).expect(201);
    expect(ai.call.mock.calls.some(([route])=>route==='ask')).toBe(false);
    const payload=ai.call.mock.calls.find(([route])=>route==='consultation')![1];
    expect(payload.contexts[0].text).toContain('LDL 4.7 mmol/L.');
    expect(payload.contexts[0].text).toContain('USER CORRECTED LDL 4.1 mmol/L');
    expect(r.body.sourceRefs[0]).toMatchObject({documentId:d.id,textVersion:1});
  });
  it('keeps rejected fact markers in an explicitly selected consultation context',async()=>{
    const d=await ready();
    await request(app.getHttpServer()).patch('/api/facts/'+d.facts[0].id).send({reviewStatus:'REJECTED'}).expect(200);
    await worker.tick();ai.call.mockClear();
    await request(app.getHttpServer()).post('/api/consultations/prepare').send({question:'Review selected findings',documentIds:[d.id]}).expect(201);
    expect(ai.call.mock.calls.find(([route])=>route==='consultation')![1].contexts[0].text).toContain('USER REJECTED LDL');
  });
  it('blocks an explicitly selected consultation if its source changes during privacy pass',async()=>{
    const d=await ready();ai.call.mockClear();
    ai.call.mockImplementation(async(route,body)=>{if(route==='consultation')await db.getRepository(Document).increment({id:d.id},'generation',1);return mock(route,body);});
    const r=await request(app.getHttpServer()).post('/api/consultations/prepare').send({question:'Selected source context',documentIds:[d.id]}).expect(409);
    expect(r.body.code).toBe('SOURCE_CHANGED');
    expect(await db.getRepository(Consultation).count()).toBe(0);
    expect(ai.call.mock.calls.some(([route])=>route==='ask')).toBe(false);
  });
  it('rejects deleted or unready explicit sources instead of silently preparing a partial selection',async()=>{
    const d=await ready(),pending=await note('Another source still queued.');
    ai.call.mockClear();
    await request(app.getHttpServer()).post('/api/consultations/prepare').send({question:'Both selected sources',documentIds:[d.id,pending.id]}).expect(400);
    await request(app.getHttpServer()).delete('/api/documents/'+d.id).expect(200);
    await request(app.getHttpServer()).post('/api/consultations/prepare').send({question:'Deleted source',documentIds:[d.id]}).expect(400);
    expect(ai.call).not.toHaveBeenCalled();
    expect(await db.getRepository(Consultation).count()).toBe(0);
  });
  it('enforces eight documents per explicit consultation',async()=>{
    await request(app.getHttpServer()).post('/api/consultations/prepare').send({question:'Too many selected documents',documentIds:Array.from({length:9},()=>randomUUID())}).expect(400);
    expect(ai.call).not.toHaveBeenCalled();
  });
  it('warns when selected source text is truncated to the consultation context limit',async()=>{
    const text='SYNTHETIC note. '+'x'.repeat(11000),d=await ready(text);
    ai.call.mockClear();
    const r=await request(app.getHttpServer()).post('/api/consultations/prepare').send({question:'Selected long source',documentIds:[d.id]}).expect(201);
    expect(r.body.warnings.some((w:string)=>w.includes('10000'))).toBe(true);
    const context=ai.call.mock.calls.find(([route])=>route==='consultation')![1].contexts[0].text;
    expect(context).toContain(text.slice(0,10000));expect(context).not.toContain(text);
  });
  it('never exports local source IDs, filenames or paths',async()=>{const d=await ready();const c=(await request(app.getHttpServer()).post('/api/consultations/prepare').send({question:'Prepare LDL context'}).expect(201)).body;const updated=(await request(app.getHttpServer()).patch('/api/consultations/'+c.id).send({content:'Dose 20 mg. '+d.id+' C:\\private\\patient.pdf'}).expect(200)).body;expect(updated.content).not.toContain(d.id);await request(app.getHttpServer()).post('/api/consultations/'+c.id+'/review').send({contentHash:updated.contentHash}).expect(201);expect((await request(app.getHttpServer()).get('/api/consultations/'+c.id+'/export').expect(200)).text).toBe(updated.content);});
  it('suppresses stale RAG answers when document generation changes even if status is READY',async()=>{const d=await ready();ai.call.mockImplementation(async(route,body)=>{if(route==='ask'){await db.getRepository(Document).increment({id:d.id},'generation',1);}return mock(route,body);});const r=await request(app.getHttpServer()).post('/api/ask').send({question:'What is LDL?'}).expect(201);expect(r.body.insufficientContext).toBe(true);expect(r.body.sources).toHaveLength(0);});
  it('rejects consultation generation if a source changes during privacy pass',async()=>{const d=await ready();ai.call.mockImplementation(async(route,body)=>{if(route==='consultation')await db.getRepository(Document).increment({id:d.id},'generation',1);return mock(route,body);});await request(app.getHttpServer()).post('/api/consultations/prepare').send({question:'Prepare LDL context'}).expect(409);expect(await db.getRepository(Consultation).count()).toBe(0);});
  it('imports clinical seed idempotently and refuses to mix a different synthetic patient',async()=>{
    process.env.SEED_ENABLED='true';process.env.SEED_DIR=resolve(__dirname,'../../seed/clinical');
    try {
      const seed=new SeedService(db);await seed.onModuleInit();await seed.onModuleInit();
      expect(await db.getRepository(Document).count()).toBe(32);
      process.env.SEED_DIR=resolve(__dirname,'../../seed');await seed.onModuleInit();
      expect(await db.getRepository(Document).count()).toBe(32);
    }finally{process.env.SEED_ENABLED='false';}
  },30000);
  it('never adds synthetic data to a pre-existing personal archive',async()=>{
    await ready();process.env.SEED_ENABLED='true';process.env.SEED_DIR=resolve(__dirname,'../../seed/clinical');
    try{await new SeedService(db).onModuleInit();expect(await db.getRepository(Document).count()).toBe(1);}
    finally{process.env.SEED_ENABLED='false';}
  });
  it('imports complete synthetic seed idempotently with original TXT and PDF files',async()=>{process.env.SEED_ENABLED='true';process.env.SEED_DIR=resolve(__dirname,'../../seed');try{const seed=new SeedService(db);await seed.onModuleInit();await seed.onModuleInit();const docs=await db.getRepository(Document).find();expect(docs).toHaveLength(36);const original=await app.get(ArchiveServiceForTest()).original(docs.find(d=>d.sourceType==='PDF')!.id);expect((await readFile(original.path)).subarray(0,5).toString()).toBe('%PDF-');const textDoc=docs.find(d=>d.sourceType==='TEXT')!;expect((await app.get(ArchiveServiceForTest()).original(textDoc.id)).mimeType).toContain('text/plain');expect((await request(app.getHttpServer()).get('/api/history?pageSize=100').expect(200)).body.total).toBeGreaterThanOrEqual(41);}finally{process.env.SEED_ENABLED='false';}},30000);
  it('recovers persisted RUNNING jobs after worker restart',async()=>{const d=await note();await db.getRepository(ProcessingJob).update(d.jobId,{status:'RUNNING'});const restarted=new ProcessingService(db,ai as any);process.env.WORKER_ENABLED='true';try{await restarted.onApplicationBootstrap();for(let n=0;n<30;n++){const job=await db.getRepository(ProcessingJob).findOneByOrFail({id:d.jobId});if(job.status==='READY')break;await new Promise(r=>setTimeout(r,30));}expect((await db.getRepository(ProcessingJob).findOneByOrFail({id:d.jobId})).status).toBe('READY');}finally{await restarted.onApplicationShutdown();process.env.WORKER_ENABLED='false';}});
});
function ArchiveServiceForTest(){return require('../src/archive.service').ArchiveService;}
