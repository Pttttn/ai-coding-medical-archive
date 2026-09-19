import {BadRequestException, ConflictException, Injectable, ServiceUnavailableException} from '@nestjs/common';
import {createHash} from 'node:crypto';
import {isAbsolute,relative,resolve} from 'node:path';

export const MAX_UPLOAD_BYTES=20*1024*1024;
export const contentHash=(text:string)=>createHash('sha256').update(text,'utf8').digest('hex');
export const normalizeTags=(tags:string[]=[])=>[...new Set(tags.map(t=>t.trim()).filter(Boolean))];
export const paginate=<T>(items:T[],total:number,page:number,pageSize:number)=>({items,total,page,pageSize});
export const safeStoragePath=(root:string,name:string)=>{
  const base=resolve(root), target=resolve(base,name), rel=relative(base,target);
  if(!rel||rel.startsWith('..')||isAbsolute(rel)) throw new BadRequestException({message:'Недопустимый путь файла',code:'INVALID_PATH'});
  return target;
};
export function validatePdf(file:Express.Multer.File|undefined):asserts file is Express.Multer.File {
  if(!file) throw new BadRequestException({message:'Выберите PDF-файл',code:'FILE_REQUIRED'});
  if(file.size>MAX_UPLOAD_BYTES) throw new BadRequestException({message:'PDF превышает 20 МиБ',code:'FILE_TOO_LARGE'});
  if(!/\.pdf$/i.test(file.originalname)||!['application/pdf','application/octet-stream'].includes(file.mimetype)||!file.buffer.subarray(0,5).equals(Buffer.from('%PDF-')))
    throw new BadRequestException({message:'Поддерживается PDF с текстовым слоем',code:'UNSUPPORTED_FILE_TYPE'});
}
export function ensureReviewed(c:{content:string;contentHash:string;reviewedHash:string|null;status:string}) {
  if(c.status!=='REVIEWED'||c.reviewedHash!==c.contentHash||contentHash(c.content)!==c.contentHash)
    throw new ConflictException({message:'Подтвердите проверку текущего текста перед экспортом',code:'REVIEW_REQUIRED'});
}
export function exportSafe(content:string):string {
  // Last boundary protects local refs even if a user manually pastes them into the draft.
  return content.replace(/\b[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}\b/gi,'[внутренняя ссылка]')
    .replace(/(?:file:\/\/\S+|[A-Za-z]:[\\/]\S+|\\\\\S+|(?<![\w:])\/(?:[\w.-]+\/)+\S+)/g,'[локальный путь]')
    .replace(/\b[^\s<>"']+\.(?:pdf|txt|docx)\b/gi,'[имя файла]');
}
export class AiError extends ServiceUnavailableException {
  constructor(public readonly safeCode:string) {super({message:ERROR_MESSAGES[safeCode]??'Локальный AI-сервис временно недоступен',code:safeCode});}
}
const ERROR_MESSAGES:Record<string,string>={
  UNSUPPORTED_OCR_REQUIRED:'В PDF нет текстового слоя; OCR не входит в MVP', MALFORMED_PDF:'PDF повреждён или не поддерживается',
  MODEL_UNAVAILABLE:'Локальная модель недоступна', EXTRACTION_INVALID:'Ответ модели не прошёл проверку структуры',
  MODEL_OUTPUT_LIMIT:'Модель исчерпала лимит ответа; попробуйте сократить запрос',
  MODEL_OUTPUT_INVALID:'Ответ модели не соответствует ожидаемой структуре',
  PRIVACY_CHECK_FAILED:'Локальная проверка приватности не завершилась успешно; повторите подготовку пакета',
  EMBEDDING_UNAVAILABLE:'Модель эмбеддингов недоступна', INDEX_UNAVAILABLE:'Поисковый индекс недоступен', AI_UNAVAILABLE:'Локальный AI-сервис недоступен',
};
@Injectable()
export class AiClient {
  async call<T=any>(route:string,body:unknown):Promise<T> {
    try {
      const response=await fetch(`${process.env.AI_BASE_URL??'http://ai:8001'}/internal/${route}`,{
        method:'POST',headers:{'Content-Type':'application/json','X-Internal-Token':process.env.INTERNAL_API_TOKEN??''},
        body:JSON.stringify(body),signal:AbortSignal.timeout(Number(process.env.AI_TIMEOUT_MS??600000)),
      });
      const data=await response.json() as any;
      if(!response.ok) throw new AiError(typeof data?.detail?.code==='string'?data.detail.code:'AI_UNAVAILABLE');
      return data as T;
    }catch(error){ if(error instanceof AiError) throw error; throw new AiError('AI_UNAVAILABLE'); }
  }
}
