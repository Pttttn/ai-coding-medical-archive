import {Injectable,OnModuleInit} from '@nestjs/common';
import {DataSource} from 'typeorm';
import {copyFile,mkdir,readFile} from 'node:fs/promises';
import {basename,resolve,extname} from 'node:path';
import {createHash} from 'node:crypto';
import {contentHash,normalizeTags,safeStoragePath} from './core';
import {audit,enqueue,ensureTags,factSnapshot,rebuildTimeline} from './archive.service';
import {Document,ExtractionRun,FactProvenance,FactRevision,MedicalFact,TextRevision} from './entities';

@Injectable()
export class SeedService implements OnModuleInit {
  constructor(private readonly db:DataSource){}
  async onModuleInit() {
    if(process.env.SEED_ENABLED!=='true')return;
    const root=resolve(process.env.SEED_DIR??'../seed');
    const records=JSON.parse(await readFile(safeStoragePath(root,'records.json'),'utf8')) as any[];
    if(!Array.isArray(records))throw new Error('Invalid synthetic seed manifest');
    const uploads=resolve(process.env.UPLOAD_DIR??'data/uploads');await mkdir(uploads,{recursive:true});
    for(const r of records) {
      if(await this.db.getRepository(Document).existsBy({id:r.id}))continue;
      let storagePath:string|null=null,hash=contentHash(r.text);
      if(r.originalFile) {
        const source=safeStoragePath(root,r.originalFile),bytes=await readFile(source);
        storagePath=safeStoragePath(uploads,r.id+(extname(r.originalFile).toLowerCase()==='.pdf'?'.pdf':'.txt'));await copyFile(source,storagePath);
        hash=createHash('sha256').update(bytes).digest('hex');
      }
      await this.db.transaction(async m=>{
        const d=await m.save(Document,m.create(Document,{id:r.id,title:r.title,documentType:r.documentType,documentDate:r.documentDate??null,sourceType:r.sourceType,originalFilename:r.originalFile?basename(r.originalFile):null,storagePath,sha256:hash,mimeType:r.originalFile?(r.sourceType==='PDF'?'application/pdf':'text/plain'):null,status:'INDEXING',summary:r.summary,tags:normalizeTags(r.tags),textVersion:1,isSeed:true,searchText:[r.title,r.summary,r.text].join('\n')}));
        await ensureTags(m,d.tags);
        const revision=await m.save(TextRevision,m.create(TextRevision,{documentId:d.id,version:1,content:r.text,pages:r.pages??[],parser:'synthetic-seed',parserVersion:'1'}));
        await audit(m,d.id,'DOCUMENT',d.id,'SYNTHETIC_SEED_IMPORTED',null,{synthetic:true,precomputed:true});
        for(const incoming of r.facts??[]) {
          const f=m.create(MedicalFact,{documentId:d.id,type:incoming.type,name:incoming.name,valueText:incoming.valueText??null,valueNumber:incoming.valueNumber??null,unit:incoming.unit??null,eventDate:incoming.eventDate??null,assertionStatus:incoming.assertionStatus??'UNKNOWN',reviewStatus:'UNREVIEWED',confidence:incoming.confidence??null,originalValue:{}});
          f.originalValue=factSnapshot(f);await m.save(f);
          await m.save(FactProvenance,m.create(FactProvenance,{factId:f.id,documentId:d.id,textRevisionId:revision.id,textVersion:1,pageNumber:incoming.provenance?.page??null,sourceText:incoming.provenance?.sourceText??''}));
          if(incoming.correction) {
            const before=factSnapshot(f);Object.assign(f,incoming.correction);f.reviewStatus='CORRECTED';await m.save(f);
            await m.save(FactRevision,m.create(FactRevision,{factId:f.id,oldValue:before,newValue:factSnapshot(f),changeType:'CORRECTED'}));
            await audit(m,d.id,'FACT',f.id,'FACT_CORRECTED',before,factSnapshot(f));
          }
        }
        await rebuildTimeline(m,d);
        await m.save(ExtractionRun,m.create(ExtractionRun,{documentId:d.id,textVersion:1,model:'synthetic-seed-precomputed',promptVersion:'seed-v1',schemaVersion:'1',parserVersion:'seed-v1',status:'READY',rawJson:{synthetic:true,precomputed:true,facts:r.facts},completedAt:new Date()}));
        await enqueue(m,d,'INDEX');
      });
    }
  }
}
