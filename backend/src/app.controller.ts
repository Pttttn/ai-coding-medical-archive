import {Body,Controller,Delete,Get,Param,ParseIntPipe,ParseUUIDPipe,Patch,Post,Query,Res,UploadedFile,UseInterceptors} from '@nestjs/common';
import {ApiBody,ApiConsumes,ApiOperation,ApiResponse,ApiTags} from '@nestjs/swagger';
import {FileInterceptor} from '@nestjs/platform-express';
import {memoryStorage} from 'multer';
import {Response} from 'express';
import {DataSource} from 'typeorm';
import {createReadStream} from 'node:fs';
import {ArchiveService} from './archive.service';
import {ConsultationService} from './consultation.service';
import {AskDto,CreateNoteDto,DocumentQueryDto,EditConsultationDto,PaginationDto,PrepareConsultationDto,ReviewDto,TagDto,TimelineQueryDto,UpdateDocumentDto,UpdateFactDto,UploadDto} from './dto';
import {MAX_UPLOAD_BYTES} from './core';

@ApiTags('Local archive')
@ApiResponse({status:400,description:'Invalid input / unsupported file / insufficient context'})
@ApiResponse({status:404,description:'Resource not found'})
@ApiResponse({status:409,description:'Duplicate document or review hash conflict'})
@ApiResponse({status:503,description:'Local AI or model unavailable'})
@Controller()
export class AppController {
  constructor(private readonly archive:ArchiveService,private readonly consultation:ConsultationService,private readonly db:DataSource){}
  @Get('health') @ApiOperation({summary:'Database-backed readiness'})
  async health(){await this.db.query('SELECT 1');return {status:'ok',service:'local-medical-archive'};}
  @Post('documents/note') @ApiOperation({summary:'Create note or visit transcript; processing is queued'})
  note(@Body()dto:CreateNoteDto){return this.archive.createNote(dto);}
  @Post('documents/upload') @ApiConsumes('multipart/form-data')
  @ApiOperation({summary:'Upload a text-based PDF, up to 20 MiB; returns document and durable job IDs'})
  @ApiBody({schema:{type:'object',required:['file','title'],properties:{file:{type:'string',format:'binary'},title:{type:'string',maxLength:200},documentDate:{type:'string',format:'date'},tags:{type:'string',example:'["анализы"]'}}}})
  @UseInterceptors(FileInterceptor('file',{storage:memoryStorage(),limits:{fileSize:MAX_UPLOAD_BYTES,files:1,fields:5,fieldSize:20000}}))
  upload(@UploadedFile()file:Express.Multer.File,@Body()dto:UploadDto){return this.archive.upload(file,dto);}
  @Get('documents') @ApiOperation({summary:'Paginated archive, trash, full-text search and filters'})
  list(@Query()q:DocumentQueryDto){return this.archive.list(q);}
  @Get('documents/:id') @ApiOperation({summary:'Document with current text, facts, immutable revision list and latest job'})
  document(@Param('id',ParseUUIDPipe)id:string){return this.archive.detail(id);}
  @Get('documents/:id/source-ir') @ApiOperation({summary:'Private source-only IR for the current immutable text revision; not a public MCP tool'})
  sourceIR(@Param('id',ParseUUIDPipe)id:string){return this.archive.sourceIR(id);}
  @Patch('documents/:id') @ApiOperation({summary:'Edit metadata or create an immutable text revision'})
  edit(@Param('id',ParseUUIDPipe)id:string,@Body()dto:UpdateDocumentDto){return this.archive.update(id,dto);}
  @Delete('documents/:id') @ApiOperation({summary:'Move to trash and queue removal from AI index'})
  remove(@Param('id',ParseUUIDPipe)id:string){return this.archive.remove(id);}
  @Post('documents/:id/restore') @ApiOperation({summary:'Restore and reindex a document'})
  restore(@Param('id',ParseUUIDPipe)id:string){return this.archive.restore(id);}
  @Post('documents/:id/reprocess') @ApiOperation({summary:'Queue local extraction while preserving reviewed facts'})
  reprocess(@Param('id',ParseUUIDPipe)id:string){return this.archive.reprocess(id);}
  @Get('documents/:id/original') @ApiOperation({summary:'Read the immutable original PDF'})
  async original(@Param('id',ParseUUIDPipe)id:string,@Res()res:Response) {
    const original=await this.archive.original(id);
    res.setHeader('Content-Type',original.mimeType);
    res.setHeader('Content-Disposition',"inline; filename=\"document.pdf\"; filename*=UTF-8''"+encodeURIComponent(original.filename));
    res.setHeader('Content-Security-Policy',"default-src 'none'; sandbox");
    const stream=createReadStream(original.path);stream.on('error',()=>res.destroy());stream.pipe(res);
  }
  @Get('documents/:id/text-revisions/:version') @ApiOperation({summary:'Read the original immutable text version referenced by provenance'})
  revision(@Param('id',ParseUUIDPipe)id:string,@Param('version',ParseIntPipe)version:number){return this.archive.revision(id,version);}
  @Get('documents/:id/facts') @ApiOperation({summary:'Active facts including source assertions and separate human review status'})
  facts(@Param('id',ParseUUIDPipe)id:string){return this.archive.facts(id);}
  @Patch('facts/:id') @ApiOperation({summary:'Correct or review a fact, preserving the original AI value and audit history'})
  fact(@Param('id',ParseUUIDPipe)id:string,@Body()dto:UpdateFactDto){return this.archive.updateFact(id,dto);}
  @Get('facts/:id/source') @ApiOperation({summary:'Exact source quote, PDF page, and immutable text revision'})
  source(@Param('id',ParseUUIDPipe)id:string){return this.archive.source(id);}
  @Get('facts/:id/history') @ApiOperation({summary:'Paginated fact revisions'})
  factHistory(@Param('id',ParseUUIDPipe)id:string,@Query()q:PaginationDto){return this.archive.factHistory(id,q);}
  @Get('timeline') @ApiOperation({summary:'Medical events; unknown dates stay null, with type/date/document filters'})
  timeline(@Query()q:TimelineQueryDto){return this.archive.timeline(q);}
  @Get('search') @ApiOperation({summary:'PostgreSQL full-text document search'})
  search(@Query()q:DocumentQueryDto){return this.archive.list(q);}
  @Post('ask') @ApiOperation({summary:'Local Corrective RAG with sources restricted to current active documents'})
  ask(@Body()dto:AskDto){return this.archive.ask(dto.question,dto.documentIds,dto.dateFrom,dto.dateTo);}
  @Get('dashboard') @ApiOperation({summary:'Counts, monthly distribution, document types, recent uploads and changes'})
  dashboard(){return this.archive.dashboard();}
  @Get('history') @ApiOperation({summary:'Paginated local audit trail'})
  history(@Query()q:PaginationDto){return this.archive.history(q);}
  @Get('documents/:id/history') @ApiOperation({summary:'Paginated audit trail of one document'})
  documentHistory(@Param('id',ParseUUIDPipe)id:string,@Query()q:PaginationDto){return this.archive.history(q,id);}
  @Get('jobs/:id') @ApiOperation({summary:'Durable processing state and safe error code'})
  job(@Param('id',ParseUUIDPipe)id:string){return this.archive.job(id);}
  @Get('tags') @ApiOperation({summary:'Tag catalogue'}) tags(){return this.archive.tags();}
  @Post('tags') @ApiOperation({summary:'Create a reusable tag'}) createTag(@Body()dto:TagDto){return this.archive.createTag(dto.name);}
  @Patch('tags/:id') @ApiOperation({summary:'Rename a tag on all linked documents'})
  editTag(@Param('id',ParseUUIDPipe)id:string,@Body()dto:TagDto){return this.archive.editTag(id,dto.name);}
  @Delete('tags/:id') @ApiOperation({summary:'Delete a tag from catalogue and documents'})
  deleteTag(@Param('id',ParseUUIDPipe)id:string){return this.archive.deleteTag(id);}
  @Post('consultations/prepare') @ApiOperation({summary:'Prepare a locally sanitized consultation draft; never sends it externally'})
  prepare(@Body()dto:PrepareConsultationDto){return this.consultation.prepare(dto);}
  @Get('consultations/:id') @ApiOperation({summary:'Local consultation preview, warnings, and source refs'})
  getConsultation(@Param('id',ParseUUIDPipe)id:string){return this.consultation.get(id);}
  @Patch('consultations/:id') @ApiOperation({summary:'Edit draft and invalidate prior review'})
  editConsultation(@Param('id',ParseUUIDPipe)id:string,@Body()dto:EditConsultationDto){return this.consultation.edit(id,dto.content);}
  @Post('consultations/:id/review') @ApiOperation({summary:'Confirm review of an exact SHA256 content version'})
  review(@Param('id',ParseUUIDPipe)id:string,@Body()dto:ReviewDto){return this.consultation.review(id,dto.contentHash);}
  @Get('consultations/:id/export') @ApiOperation({summary:'Export the exact reviewed Markdown; 409 before review or after any edit'})
  async export(@Param('id',ParseUUIDPipe)id:string,@Res()res:Response) {
    const markdown=await this.consultation.export(id);
    res.setHeader('Content-Type','text/markdown; charset=utf-8');
    res.setHeader('Content-Disposition','attachment; filename="consultation.md"');
    res.send(markdown);
  }
}
