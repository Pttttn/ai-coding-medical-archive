import {ConflictException,Injectable,NotFoundException,BadRequestException} from '@nestjs/common';
import {DataSource,In,IsNull} from 'typeorm';
import {ArchiveService,audit} from './archive.service';
import {AiClient,contentHash,ensureReviewed,exportSafe} from './core';
import {Consultation,Document,MedicalFact,TextRevision} from './entities';
import {PrepareConsultationDto} from './dto';

const sameSnapshots=(expected:Document[],current:Document[])=>current.length===expected.length&&expected.every(d=>current.some(n=>n.id===d.id&&n.generation===d.generation&&n.textVersion===d.textVersion));
const sourceChanged=()=>new ConflictException({message:'Источники изменились. Подготовьте пакет повторно.',code:'SOURCE_CHANGED'});

@Injectable()
export class ConsultationService {
  constructor(private readonly db:DataSource,private readonly ai:AiClient,private readonly archive:ArchiveService){}
  async get(id:string){const c=await this.db.getRepository(Consultation).findOneBy({id});if(!c)throw new NotFoundException('Консультация не найдена');return c;}
  async prepare(dto:PrepareConsultationDto) {
    // Explicit selection already expresses the user's relevance decision; QA generation is
    // needed only for automatic selection and must not veto an explicitly chosen source.
    const explicit=Boolean(dto.documentIds?.length);
    if((dto.documentIds?.length??0)>8)throw new BadRequestException({message:'Выберите не более 8 документов для одного пакета',code:'CONTEXT_LIMIT'});
    const answer=explicit?null:await this.archive.ask(dto.question);
    const ids=explicit?[...new Set(dto.documentIds!)]:[...new Set<string>((answer?.sources??[]).map((s:any)=>s.documentId).filter(Boolean))].slice(0,8);
    if(!ids.length)throw new BadRequestException({message:'Не найдены релевантные готовые документы. Уточните вопрос.',code:'INSUFFICIENT_CONTEXT'});
    const found=await this.db.getRepository(Document).findBy({id:In(ids),deletedAt:IsNull(),status:'READY'});
    if(found.length!==ids.length) {
      if(explicit)throw new BadRequestException({message:'Один из выбранных документов удалён или ещё не готов. Обновите выбор.',code:'SOURCE_UNAVAILABLE'});
      throw sourceChanged();
    }
    const docs=ids.map(id=>found.find(d=>d.id===id)!);
    if(!explicit&&docs.some(d=>(answer?.sources??[]).some((s:any)=>s.documentId===d.id&&(s.generation!==d.generation||s.textVersion!==d.textVersion))))throw sourceChanged();
    const contexts:{text:string}[]=[];
    const contextWarnings:string[]=[];
    for(const [index,d] of docs.entries()) {
      const snippets=(answer?.sources??[]).filter((s:any)=>s.documentId===d.id&&typeof s.text==='string').map((s:any)=>s.text);
      let text=snippets.join('\n');
      if(!text)text=(await this.db.getRepository(TextRevision).findOneBy({documentId:d.id,version:d.textVersion}))?.content??'';
      if(!text.trim())throw new BadRequestException({message:'Выбранный документ не содержит доступного текста.',code:'SOURCE_UNAVAILABLE'});
      if(text.length>10000)contextWarnings.push('Документ '+(index+1)+': исходный контекст ограничен первыми 10000 символами. Проверьте полноту медицинских сведений.');
      const corrections=await this.db.getRepository(MedicalFact).findBy({documentId:d.id,active:true,reviewStatus:In(['CONFIRMED','CORRECTED','REJECTED'])});
      const corrected=corrections.map(f=>['USER '+f.reviewStatus,f.name,f.valueText,f.valueNumber,f.unit].filter(v=>v!=null).join(' ')).join('\n');
      contexts.push({text:[d.documentDate?'Medical date: '+d.documentDate:'Medical date: unknown',text.slice(0,10000),corrected].filter(Boolean).join('\n')});
    }
    // Text and facts were read using the captured versions. Refuse a race before inference,
    // and check again under DB locks before saving the generated package.
    const beforePrivacy=await this.db.getRepository(Document).findBy({id:In(ids),deletedAt:IsNull(),status:'READY'});
    if(!sameSnapshots(docs,beforePrivacy))throw sourceChanged();
    const result=await this.ai.call<{content:string;warnings:string[]}>('consultation',{question:dto.question,contexts});
    if(typeof result.content!=='string'||!result.content.trim()||!Array.isArray(result.warnings)||result.warnings.some(w=>typeof w!=='string'))throw new BadRequestException({message:'Privacy pass не вернул корректный текст',code:'PRIVACY_CHECK_FAILED'});
    return this.db.transaction(async m=>{
      const latest=await m.getRepository(Document).createQueryBuilder('d').where('d.id IN (:...ids) AND d."deletedAt" IS NULL AND d.status = :status',{ids,status:'READY'}).orderBy('d.id','ASC').setLock('pessimistic_read').getMany();
      if(!sameSnapshots(docs,latest))throw sourceChanged();
      const content=exportSafe(result.content);
      const c=await m.getRepository(Consultation).save({question:dto.question,content,contentHash:contentHash(content),reviewedHash:null,status:'NEEDS_REVIEW',warnings:[...contextWarnings,...result.warnings,'Проверьте весь текст вручную: автоматическая очистка не гарантирует анонимность.'],sourceRefs:docs.map(d=>({documentId:d.id,title:d.title,textVersion:d.textVersion,generation:d.generation})),contexts,generationVersion:'privacy-v1'});
      await audit(m,null,'CONSULTATION',c.id,'CONSULTATION_PREPARED',null,{contentHash:c.contentHash,sourceCount:docs.length});
      return c;
    });
  }
  async edit(id:string,raw:string) {
    return this.db.transaction(async m=>{
      const c=await m.getRepository(Consultation).findOne({where:{id},lock:{mode:'pessimistic_write'}});
      if(!c)throw new NotFoundException('Консультация не найдена');
      c.content=exportSafe(raw);c.contentHash=contentHash(c.content);c.reviewedHash=null;c.status='NEEDS_REVIEW';
      await m.save(c);await audit(m,null,'CONSULTATION',id,'CONSULTATION_EDITED',null,{contentHash:c.contentHash});return c;
    });
  }
  async review(id:string,hash:string) {
    return this.db.transaction(async m=>{
      const c=await m.getRepository(Consultation).findOne({where:{id},lock:{mode:'pessimistic_write'}});
      if(!c)throw new NotFoundException('Консультация не найдена');
      if(c.contentHash!==hash||contentHash(c.content)!==hash)throw new ConflictException({message:'Текст изменился. Просмотрите текущую версию.',code:'CONTENT_CHANGED'});
      c.reviewedHash=hash;c.status='REVIEWED';await m.save(c);
      await audit(m,null,'CONSULTATION',id,'CONSULTATION_REVIEWED',null,{contentHash:hash});return c;
    });
  }
  async export(id:string) {
    const c=await this.get(id);ensureReviewed(c);
    if(exportSafe(c.content)!==c.content)throw new ConflictException({message:'Текст содержит внутренние ссылки; исправьте и проверьте его повторно.',code:'PRIVACY_CHECK_FAILED'});
    await audit(this.db.manager,null,'CONSULTATION',id,'CONSULTATION_EXPORTED',null,{contentHash:c.contentHash});
    return c.content;
  }
}
