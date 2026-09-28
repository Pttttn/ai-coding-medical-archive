import {BadRequestException,ConflictException,Injectable,NotFoundException} from '@nestjs/common';
import {createHash} from 'node:crypto';
import {DataSource,EntityManager} from 'typeorm';
import {readFile,readdir,realpath,unlink} from 'node:fs/promises';
import {join,relative,isAbsolute,resolve} from 'node:path';
import {Document} from './entities';
import {AiClient} from './core';
import {audit} from './archive.service';
import {PurgeDocumentDto} from './dto';

// Files the application itself names: seed ids and uploads are UUID-named. Nothing else is ever deleted by hash.
const ORIGINAL_NAME=/^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\.(?:pdf|txt)$/;
const uploadRoot=()=>resolve(process.env.UPLOAD_DIR??'data/uploads');

/** Permanent deletion of a document from the trash: original file, every revision, facts, index and history. */
@Injectable()
export class PurgeService {
  constructor(private readonly db:DataSource,private readonly ai:AiClient){}

  // Consultations whose prepared context was built from this document.
  private async consultations(m:EntityManager,id:string):Promise<{id:string;question:string;createdAt:Date;responseCount:number}[]> {
    return m.query(`SELECT c.id,c.question,c."createdAt",(SELECT count(*)::int FROM consultation_responses r WHERE r."consultationId"=c.id) AS "responseCount"
      FROM consultations c WHERE c."sourceRefs" @> $1::jsonb OR EXISTS (SELECT 1 FROM consultation_prompts p WHERE p."consultationId"=c.id AND p."sourceRefs" @> $1::jsonb)
      ORDER BY c."createdAt",c.id`,[JSON.stringify([{documentId:id}])]);
  }
  private async trashed(m:EntityManager,id:string,lock=false):Promise<Document> {
    const qb=m.getRepository(Document).createQueryBuilder('d').addSelect('d.storagePath').where('d.id = :id',{id});
    if(lock)qb.setLock('pessimistic_write');
    const doc=await qb.getOne();
    if(!doc)throw new NotFoundException({message:'Документ не найден',code:'DOCUMENT_NOT_FOUND'});
    if(!doc.deletedAt)throw new ConflictException({message:'Удалить навсегда можно только документ из корзины',code:'DOCUMENT_NOT_IN_TRASH'});
    return doc;
  }

  async preview(id:string) {
    const doc=await this.trashed(this.db.manager,id);
    return {id:doc.id,title:doc.title,consultations:await this.consultations(this.db.manager,id)};
  }

  async purge(id:string,dto:PurgeDocumentDto) {
    const before=await this.trashed(this.db.manager,id);
    if(dto.confirmTitle!==before.title)throw new BadRequestException({message:'Название для подтверждения не совпадает',code:'PURGE_NOT_CONFIRMED'});
    // The index is cleared first: if the AI service is unavailable nothing is deleted and the request can be repeated.
    await this.ai.call('remove',{documentId:id,purge:true});
    const {consultationIds}=await this.db.transaction(async m=>{
      const doc=await this.trashed(m,id,true);
      if(doc.generation!==before.generation)throw new ConflictException({message:'Документ изменился; повторите удаление',code:'DOCUMENT_CHANGED'});
      const linked=(await this.consultations(m,id)).map(c=>c.id);
      const confirmed=[...new Set(dto.consultationIds)].sort();
      if(linked.length!==confirmed.length||linked.some(c=>!confirmed.includes(c)))
        throw new ConflictException({message:'Список связанных консультаций изменился; проверьте его снова',code:'PURGE_CONSULTATIONS_CHANGED'});
      await m.query('UPDATE documents SET "activeProcessingRevisionId"=NULL WHERE id=$1',[id]);
      for(const sql of [
        'DELETE FROM timeline_events WHERE "documentId"=$1',
        'DELETE FROM fact_revisions WHERE "factId" IN (SELECT id FROM medical_facts WHERE "documentId"=$1)',
        'DELETE FROM fact_provenance WHERE "documentId"=$1 OR "factId" IN (SELECT id FROM medical_facts WHERE "documentId"=$1)',
        'DELETE FROM processing_jobs WHERE "documentId"=$1',
        'DELETE FROM medical_facts WHERE "documentId"=$1',
        'DELETE FROM processing_revisions WHERE "documentId"=$1',
        'DELETE FROM extraction_runs WHERE "documentId"=$1',
        'DELETE FROM source_ir_revisions WHERE "documentId"=$1',
        'DELETE FROM text_revisions WHERE "documentId"=$1',
        'DELETE FROM audit_events WHERE "documentId"=$1',
      ])await m.query(sql,[id]);
      if(linked.length){
        await m.query('DELETE FROM consultation_responses WHERE "consultationId"=ANY($1::uuid[])',[linked]);
        await m.query('DELETE FROM consultation_prompts WHERE "consultationId"=ANY($1::uuid[])',[linked]);
        await m.query(`DELETE FROM audit_events WHERE "entityType"='CONSULTATION' AND "entityId"=ANY($1::uuid[])`,[linked]);
        await m.query('DELETE FROM consultations WHERE id=ANY($1::uuid[])',[linked]);
      }
      await m.query('DELETE FROM documents WHERE id=$1',[id]);
      // The trace keeps only that a document was purged, never its title or content.
      await audit(m,null,'DOCUMENT',id,'DOCUMENT_PURGED',null,{consultationsDeleted:linked.length});
      await this.deleteOriginal(m,doc);
      return {consultationIds:linked};
    });
    return {id,purged:true,consultationsDeleted:consultationIds.length};
  }

  /**
   * Deletes the original inside the purge transaction, just before commit: if the commit then fails the
   * document is still in the trash without its file and a repeated purge completes. Processing on an older
   * build could clear storagePath while the file stayed on disk, so a PDF without a path is found by its
   * SHA-256 among application-named files that no other document references.
   */
  private async deleteOriginal(m:EntityManager,doc:Document) {
    const root=await realpath(uploadRoot()).catch(()=>null);
    if(!root)return;
    const inside=(path:string)=>{const rel=relative(root,path);return !!rel&&!rel.startsWith('..')&&!isAbsolute(rel);};
    if(doc.storagePath){
      const path=await realpath(doc.storagePath).catch(()=>null);
      if(path&&inside(path))await unlink(path);
      return;
    }
    if(doc.sourceType!=='PDF'||!doc.sha256)return;
    // A file shared by content with another document is never deleted by hash.
    if((await m.query('SELECT 1 FROM documents WHERE sha256=$1 AND id<>$2 LIMIT 1',[doc.sha256,doc.id])).length)return;
    const known=new Set<string>((await m.query('SELECT "storagePath" FROM documents WHERE "storagePath" IS NOT NULL')).map((r:{storagePath:string})=>resolve(r.storagePath)));
    for(const name of await readdir(root)){
      const path=join(root,name);
      if(!ORIGINAL_NAME.test(name)||known.has(path)||known.has(resolve(uploadRoot(),name)))continue;
      if(createHash('sha256').update(await readFile(path)).digest('hex')===doc.sha256)await unlink(path);
    }
  }
}
