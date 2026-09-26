import {Transform, Type} from 'class-transformer';
import {ArrayMaxSize, IsArray, IsDateString, IsIn, IsInt, IsNumber, IsOptional, IsString, IsUUID, Length, Matches, Max, MaxLength, Min, ValidateIf} from 'class-validator';
import {ApiProperty, ApiPropertyOptional} from '@nestjs/swagger';
import {ASSERTION_STATUSES,DOCUMENT_TYPES,FACT_TYPES,REVIEW_STATUSES,STATUSES} from './entities';

export class PaginationDto {
  @ApiPropertyOptional({default:1,minimum:1}) @Type(()=>Number) @IsInt() @Min(1) page=1;
  @ApiPropertyOptional({default:20,minimum:1,maximum:100}) @Type(()=>Number) @IsInt() @Min(1) @Max(100) pageSize=20;
}
export class DocumentQueryDto extends PaginationDto {
  @ApiPropertyOptional() @IsOptional() @IsString() @MaxLength(500) q?:string;
  @ApiPropertyOptional({enum:DOCUMENT_TYPES}) @IsOptional() @IsIn(DOCUMENT_TYPES) type?:string;
  @ApiPropertyOptional() @IsOptional() @IsString() @MaxLength(80) tag?:string;
  @ApiPropertyOptional({enum:STATUSES}) @IsOptional() @IsIn(STATUSES) status?:string;
  @ApiPropertyOptional({format:'date'}) @IsOptional() @IsDateString({strict:true}) from?:string;
  @ApiPropertyOptional({format:'date'}) @IsOptional() @IsDateString({strict:true}) to?:string;
  @ApiPropertyOptional({enum:['true','false','all']}) @IsOptional() @IsIn(['true','false','all']) deleted='false';
  @ApiPropertyOptional({enum:['createdAt','documentDate','title','status']}) @IsOptional() @IsIn(['createdAt','documentDate','title','status']) sort='createdAt';
  @ApiPropertyOptional({enum:['ASC','DESC']}) @IsOptional() @IsIn(['ASC','DESC']) order:'ASC'|'DESC'='DESC';
}
export class CreateNoteDto {
  @ApiProperty({maxLength:200}) @IsString() @Length(1,200) @Matches(/\S/) title:string;
  @ApiProperty({enum:['NOTE','VISIT_TRANSCRIPT']}) @IsIn(['NOTE','VISIT_TRANSCRIPT']) documentType='NOTE';
  @ApiProperty({maxLength:200000}) @IsString() @Length(3,200000) @Matches(/\S/) text:string;
  @ApiPropertyOptional({nullable:true,format:'date'}) @IsOptional() @IsDateString({strict:true}) documentDate?:string|null;
  @ApiPropertyOptional({type:[String]}) @IsOptional() @IsArray() @ArrayMaxSize(30) @IsString({each:true}) @Length(1,80,{each:true}) tags?:string[];
}
export class UploadDto {
  @ApiProperty({maxLength:200}) @IsString() @Length(1,200) @Matches(/\S/) title:string;
  @ApiPropertyOptional({format:'date'}) @Transform(({value})=>value===''?undefined:value) @IsOptional() @IsDateString({strict:true}) documentDate?:string;
  @ApiPropertyOptional({type:[String],description:'JSON array in multipart form'})
  @Transform(({value})=> { if(typeof value!=='string') return value; try{return JSON.parse(value);}catch{return value;} })
  @IsOptional() @IsArray() @ArrayMaxSize(30) @IsString({each:true}) @Length(1,80,{each:true}) tags?:string[];
}
export class UpdateDocumentDto {
  @ApiPropertyOptional() @ValidateIf((_,v)=>v!==undefined) @IsString() @Length(1,200) @Matches(/\S/) title?:string;
  @ApiPropertyOptional({enum:DOCUMENT_TYPES}) @ValidateIf((_,v)=>v!==undefined) @IsIn(DOCUMENT_TYPES) documentType?:string;
  @ApiPropertyOptional({nullable:true,format:'date'}) @IsOptional() @IsDateString({strict:true}) documentDate?:string|null;
  @ApiPropertyOptional() @ValidateIf((_,v)=>v!==undefined) @IsString() @Length(3,200000) @Matches(/\S/) text?:string;
  @ApiPropertyOptional() @ValidateIf((_,v)=>v!==undefined) @IsString() @MaxLength(10000) summary?:string;
  @ApiPropertyOptional({type:[String]}) @ValidateIf((_,v)=>v!==undefined) @IsArray() @ArrayMaxSize(30) @IsString({each:true}) @Length(1,80,{each:true}) tags?:string[];
}
export class UpdateFactDto {
  @ApiPropertyOptional() @ValidateIf((_,v)=>v!==undefined) @IsString() @Length(1,300) @Matches(/\S/) name?:string;
  @ApiPropertyOptional({nullable:true}) @IsOptional() @IsString() @MaxLength(10000) valueText?:string|null;
  @ApiPropertyOptional({nullable:true}) @IsOptional() @IsNumber({allowNaN:false,allowInfinity:false}) valueNumber?:number|null;
  @ApiPropertyOptional({nullable:true}) @IsOptional() @IsString() @MaxLength(100) unit?:string|null;
  @ApiPropertyOptional({nullable:true,format:'date'}) @IsOptional() @IsDateString({strict:true}) eventDate?:string|null;
  @ApiPropertyOptional({enum:FACT_TYPES}) @ValidateIf((_,v)=>v!==undefined) @IsIn(FACT_TYPES) type?:string;
  @ApiPropertyOptional({enum:ASSERTION_STATUSES}) @ValidateIf((_,v)=>v!==undefined) @IsIn(ASSERTION_STATUSES) assertionStatus?:string;
  @ApiPropertyOptional({enum:REVIEW_STATUSES}) @ValidateIf((_,v)=>v!==undefined) @IsIn(REVIEW_STATUSES) reviewStatus?:string;
}
export class TimelineQueryDto extends PaginationDto {
  @ApiPropertyOptional() @IsOptional() @IsString() @MaxLength(80) type?:string;
  @ApiPropertyOptional() @IsOptional() @IsString() @MaxLength(80) category?:string;
  @ApiPropertyOptional({format:'uuid'}) @IsOptional() @IsUUID() documentId?:string;
  @ApiPropertyOptional({format:'date'}) @IsOptional() @IsDateString({strict:true}) from?:string;
  @ApiPropertyOptional({format:'date'}) @IsOptional() @IsDateString({strict:true}) to?:string;
}
export class AskDto {
  @ApiPropertyOptional({format:'date'}) @IsOptional() @Matches(/^\d{4}-\d{2}-\d{2}$/) @IsDateString({strict:true}) dateFrom?:string;
  @ApiPropertyOptional({format:'date'}) @IsOptional() @Matches(/^\d{4}-\d{2}-\d{2}$/) @IsDateString({strict:true}) dateTo?:string;
  @ApiProperty() @IsString() @Length(3,4000) @Matches(/\S/) question:string;
  @ApiPropertyOptional({type:[String]}) @IsOptional() @IsArray() @ArrayMaxSize(100) @IsUUID('all',{each:true}) documentIds?:string[];
}
export class PrepareConsultationDto extends AskDto {
  @ApiPropertyOptional({type:[String],maxItems:8,description:'Explicit ready source documents; omitted for automatic RAG selection'})
  @ArrayMaxSize(8) declare documentIds?:string[];
}
export class TagDto {
  @ApiProperty() @IsString() @Length(1,80) @Matches(/\S/) name:string;
}
export class EditConsultationDto {
  @ApiProperty() @IsString() @Length(1,100000) @Matches(/\S/) content:string;
}
export class ReviewDto {
  @ApiProperty({description:'SHA256 of the exact previewed UTF-8 content'}) @IsString() @Matches(/^[a-f0-9]{64}$/) contentHash:string;
}

export class ConsultationQueryDto extends PaginationDto {
  @ApiPropertyOptional() @IsOptional() @IsString() @MaxLength(500) q?:string;
}
export class AddConsultationResponseDto {
  @ApiProperty({description:'Client-generated idempotency UUID'}) @IsUUID() id:string;
  @ApiProperty() @IsUUID() promptId:string;
  @ApiProperty() @IsString() @Length(1,200) @Matches(/\S/) model:string;
  @ApiProperty() @IsString() @Length(1,100000) @Matches(/\S/) content:string;
}
export class PurgeDocumentDto {
  @ApiProperty({description:'Exact document title, typed by the user to confirm permanent deletion'}) @IsString() @Length(1,200) confirmTitle:string;
  @ApiProperty({description:'Every consultation built from this document, as listed by the purge preview; they are deleted too',type:[String]})
  @IsArray() @ArrayMaxSize(1000) @IsUUID('all',{each:true}) consultationIds:string[];
}
