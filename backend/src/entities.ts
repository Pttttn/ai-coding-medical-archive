import { Column, CreateDateColumn, Entity, Index, PrimaryGeneratedColumn,PrimaryColumn, UpdateDateColumn } from 'typeorm';

export const DOCUMENT_TYPES = ['LAB_REPORT','VISIT','VISIT_TRANSCRIPT','DISCHARGE_SUMMARY','PRESCRIPTION','IMAGING_REPORT','PROCEDURE_REPORT','NOTE','OTHER'] as const;
export const FACT_TYPES = ['CONDITION','SYMPTOM','MEDICATION','LAB_RESULT','PROCEDURE','RECOMMENDATION','OBSERVATION','OTHER'] as const;
export const STATUSES = ['UPLOADED','PARSING','EXTRACTING','INDEXING','READY','FAILED','UNSUPPORTED_OCR_REQUIRED'] as const;
export const REVIEW_STATUSES = ['UNREVIEWED','CONFIRMED','CORRECTED','REJECTED'] as const;
export const ASSERTION_STATUSES = ['CONFIRMED','SUSPECTED','NEGATED','PRESCRIBED','UNKNOWN'] as const;
export type Page = {pageNumber:number|null;text:string};

@Entity('documents')
export class Document {
  @PrimaryGeneratedColumn('uuid') id: string;
  @Column() title: string;
  @Column({default:'OTHER'}) documentType: string;
  @Column({type:'date',nullable:true}) documentDate: string|null;
  @Column({default:'TEXT'}) sourceType: string;
  @Column({type:'text',nullable:true}) originalFilename: string|null;
  @Column({type:'text',nullable:true,select:false}) storagePath: string|null;
  @Column({type:'text',nullable:true}) sha256: string|null;
  @Column({type:'text',nullable:true}) mimeType: string|null;
  @Column({default:'UPLOADED'}) status: string;
  @Column({type:'text',default:''}) summary: string;
  @Column('text',{array:true,default:'{}'}) tags: string[];
  @Column({default:0}) textVersion: number;
  @Column({default:1}) generation: number;
  /** Processing revision whose facts and chunks are the document's current snapshot; null for legacy processing. */
  @Column({type:'uuid',nullable:true}) activeProcessingRevisionId: string|null;
  @Column({type:'text',default:'',select:false}) searchText: string;
  @Column({type:'text',nullable:true}) errorCode: string|null;
  @Column({default:false}) isSeed: boolean;
  @CreateDateColumn({type:'timestamptz'}) createdAt: Date;
  @UpdateDateColumn({type:'timestamptz'}) updatedAt: Date;
  @Column({type:'timestamptz',nullable:true}) deletedAt: Date|null;
}
@Entity('text_revisions')
@Index(['documentId','version'],{unique:true})
export class TextRevision {
  @PrimaryGeneratedColumn('uuid') id:string;
  @Column('uuid') documentId:string;
  @Column() version:number;
  @Column('text') content:string;
  @Column('jsonb',{default:[]}) pages:Page[];
  @Column({default:'user-text'}) parser:string;
  @Column({default:'1'}) parserVersion:string;
  @CreateDateColumn({type:'timestamptz'}) createdAt:Date;
}
@Entity('tags')
export class Tag {
  @PrimaryGeneratedColumn('uuid') id:string;
  @Column({unique:true}) name:string;
  @CreateDateColumn({type:'timestamptz'}) createdAt:Date;
}
@Entity('medical_facts')
export class MedicalFact {
  @PrimaryGeneratedColumn('uuid') id:string;
  @Index() @Column('uuid') documentId:string;
  @Column() type:string;
  @Column() name:string;
  @Column({type:'text',nullable:true}) valueText:string|null;
  @Column({type:'double precision',nullable:true}) valueNumber:number|null;
  @Column({type:'text',nullable:true}) unit:string|null;
  @Column({type:'date',nullable:true}) eventDate:string|null;
  @Column({default:'UNKNOWN'}) assertionStatus:string;
  @Column({default:'UNREVIEWED'}) reviewStatus:string;
  @Column({default:true}) aiGenerated:boolean;
  @Column({type:'double precision',nullable:true}) confidence:number|null;
  @Column('jsonb') originalValue:Record<string,unknown>;
  @Column({default:true}) active:boolean;
  @Column({type:'uuid',nullable:true}) processingRevisionId:string|null;
  @CreateDateColumn({type:'timestamptz'}) createdAt:Date;
  @UpdateDateColumn({type:'timestamptz'}) updatedAt:Date;
}
@Entity('fact_provenance')
export class FactProvenance {
  @PrimaryGeneratedColumn('uuid') id:string;
  @Index({unique:true}) @Column('uuid') factId:string;
  @Column('uuid') documentId:string;
  @Column('uuid') textRevisionId:string;
  @Column() textVersion:number;
  @Column({type:'integer',nullable:true}) pageNumber:number|null;
  @Column('text') sourceText:string;
  @CreateDateColumn({type:'timestamptz'}) createdAt:Date;
}
@Entity('fact_revisions')
export class FactRevision {
  @PrimaryGeneratedColumn('uuid') id:string;
  @Index() @Column('uuid') factId:string;
  @Column('jsonb') oldValue:Record<string,unknown>;
  @Column('jsonb') newValue:Record<string,unknown>;
  @Column() changeType:string;
  @CreateDateColumn({type:'timestamptz'}) createdAt:Date;
}
@Entity('audit_events')
export class AuditEvent {
  @PrimaryGeneratedColumn('uuid') id:string;
  @Column() entityType:string;
  @Column('uuid') entityId:string;
  @Index() @Column({type:'uuid',nullable:true}) documentId:string|null;
  @Column() action:string;
  @Column({type:'jsonb',nullable:true}) payloadBefore:unknown;
  @Column({type:'jsonb',nullable:true}) payloadAfter:unknown;
  @CreateDateColumn({type:'timestamptz'}) createdAt:Date;
}
@Entity('timeline_events')
export class TimelineEvent {
  @PrimaryGeneratedColumn('uuid') id:string;
  @Index() @Column('uuid') documentId:string;
  @Column({type:'uuid',nullable:true}) factId:string|null;
  @Column() eventType:string;
  @Column({type:'date',nullable:true}) eventDate:string|null;
  @Column() title:string;
  @Column('text') description:string;
  @CreateDateColumn({type:'timestamptz'}) createdAt:Date;
}
export const REPROCESS_MODES=['CURRENT_TEXT','ORIGINAL'] as const;
export type ReprocessMode=typeof REPROCESS_MODES[number];
@Entity('processing_jobs')
export class ProcessingJob {
  @PrimaryGeneratedColumn('uuid') id:string;
  @Index() @Column('uuid') documentId:string;
  @Column() operation:string;
  @Column({default:'QUEUED'}) status:string;
  @Column({default:0}) attempt:number;
  @Column() generation:number;
  @Column({type:'text',nullable:true}) errorCode:string|null;
  @Column({type:'timestamptz',nullable:true}) availableAt:Date|null;
  /** Parse stage stored for this job; a retry extracts from it instead of parsing again. */
  @Column({type:'uuid',nullable:true}) sourceIrRevisionId:string|null;
  /** Prepared processing revision of this job; a retry indexes and activates it instead of extracting again. */
  @Column({type:'uuid',nullable:true}) processingRevisionId:string|null;
  /** Parse source a reprocess asked for; null keeps the automatic choice (original PDF unless the text was edited). */
  @Column({type:'varchar',nullable:true}) parseSource:ReprocessMode|null;
  @CreateDateColumn({type:'timestamptz'}) createdAt:Date;
  @UpdateDateColumn({type:'timestamptz'}) updatedAt:Date;
}
@Entity('extraction_runs')
export class ExtractionRun {
  @PrimaryGeneratedColumn('uuid') id:string;
  @Column('uuid') documentId:string;
  @Column() textVersion:number;
  @Column({type:'text',nullable:true}) model:string|null;
  @Column({type:'text',nullable:true}) modelDigest:string|null;
  @Column({type:'text',nullable:true}) promptVersion:string|null;
  @Column({type:'text',nullable:true}) schemaVersion:string|null;
  @Column({type:'text',nullable:true}) parserVersion:string|null;
  @Column({type:'uuid',nullable:true}) sourceIrRevisionId:string|null;
  @Column({type:'varchar',length:64,nullable:true}) recipeHash:string|null;
  @Column() status:string;
  @Column({type:'jsonb',nullable:true}) rawJson:unknown;
  @Column({type:'jsonb',default:[]}) validationErrors:string[];
  @Column({type:'timestamptz',nullable:true}) completedAt:Date|null;
  @CreateDateColumn({type:'timestamptz'}) createdAt:Date;
}
@Entity('consultations')
export class Consultation {
  @PrimaryGeneratedColumn('uuid') id:string;
  @Column('text') question:string;
  @Column('text') content:string;
  @Column() contentHash:string;
  @Column({type:'text',nullable:true}) reviewedHash:string|null;
  @Column({default:'NEEDS_REVIEW'}) status:string;
  @Column('jsonb',{default:[]}) warnings:string[];
  @Column('jsonb',{default:[]}) sourceRefs:unknown[];
  @Column('jsonb',{default:[]}) contexts:{text:string}[];
  @Column({default:'1'}) generationVersion:string;
  @CreateDateColumn({type:'timestamptz'}) createdAt:Date;
  @UpdateDateColumn({type:'timestamptz'}) updatedAt:Date;
}
@Entity('consultation_prompts')
export class ConsultationPrompt {
  @PrimaryGeneratedColumn('uuid') id:string;
  @Column('uuid') consultationId:string;
  @Column('text') content:string;
  @Column() contentHash:string;
  @Column('jsonb') sourceRefs:unknown[];
  @CreateDateColumn({type:'timestamptz'}) createdAt:Date;
}
@Entity('consultation_responses')
export class ConsultationResponse {
  @PrimaryColumn('uuid') id:string;
  @Column('uuid') consultationId:string;
  @Column('uuid') promptId:string;
  @Column('text') model:string;
  @Column('text') content:string;
  @CreateDateColumn({type:'timestamptz'}) createdAt:Date;
}
@Entity('processing_revisions')
export class ProcessingRevision {
  @PrimaryGeneratedColumn('uuid') id:string;
  @Column('uuid') documentId:string;
  @Column('uuid') sourceIrRevisionId:string;
  @Column('uuid') textRevisionId:string;
  @Column('uuid') extractionRunId:string;
  @Column({type:'varchar',length:64}) recipeHash:string;
  @Column({default:'PREPARED'}) status:'PREPARED'|'ACTIVE'|'SUPERSEDED'|'FAILED';
  @Column({type:'jsonb',nullable:true}) indexManifest:{revisionId:string;documentChunks:number;contentHash:string|null;indexSettings?:Record<string,any>|null}|null;
  @CreateDateColumn({type:'timestamptz'}) createdAt:Date;
  @Column({type:'timestamptz',nullable:true}) activatedAt:Date|null;
}
export const ENTITIES = [ProcessingRevision,Document,TextRevision,Tag,MedicalFact,FactProvenance,FactRevision,AuditEvent,TimelineEvent,ProcessingJob,ExtractionRun,Consultation,ConsultationPrompt,ConsultationResponse];
