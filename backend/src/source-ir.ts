import {createHash} from 'node:crypto';
import {TextDecoder} from 'node:util';
import {Page} from './entities';
import {AiError} from './core';

type Span={pageIndex:number;startByte:number;endByte:number};
type Mapping={normalizedStartByte:number;normalizedEndByte:number;source:Span;operation:'IDENTITY'|'WHITESPACE'};
export type SourceIR={schemaVersion:'source-ir-v1';stage:'SOURCE_ONLY';documentId:string;parserVersion:string;normalizerVersion:'whitespace-map-v1';sourceHash:string;pages:Page[];blocks:{blockId:string;kind:'paragraph'|'separator';source:Span;normalizedText:string;mapping:Mapping[]}[];irHash:string};
const canonical=(v:any):string=>JSON.stringify(v&&typeof v==='object'?Array.isArray(v)?v.map(x=>JSON.parse(canonical(x))):Object.fromEntries(Object.keys(v).sort().map(k=>[k,JSON.parse(canonical(v[k]))])):v);
export const irHash=(value:unknown)=>createHash('sha256').update(canonical(value)).digest('hex');
const decoder=new TextDecoder('utf-8',{fatal:true});
export function validateSourceIR(input:unknown,documentId:string,pages:Page[]):asserts input is SourceIR {
  const fail=()=>{throw new AiError('SOURCE_IR_INVALID');};
  try {
    const keys=(v:unknown,expected:string[])=>{if(!v||typeof v!=='object'||Array.isArray(v)||Object.keys(v).sort().join(',')!==expected.sort().join(','))fail();};
    const ir=input as SourceIR;
    keys(ir,['schemaVersion','stage','documentId','parserVersion','normalizerVersion','sourceHash','pages','blocks','irHash']);
    if(!ir||ir.schemaVersion!=='source-ir-v1'||ir.stage!=='SOURCE_ONLY'||ir.normalizerVersion!=='whitespace-map-v1'||typeof ir.parserVersion!=='string'||ir.documentId!==documentId||!Array.isArray(ir.pages)||canonical(ir.pages)!==canonical(pages)||ir.sourceHash!==irHash(pages))fail();
    const {irHash:hash,...body}=ir;
    if(hash!==irHash(body)||!Array.isArray(ir.blocks))fail();
    for(const page of ir.pages)keys(page,['pageNumber','text']);
    const source=pages.map(p=>Buffer.from(p.text));
    const ends=pages.map(()=>0),ids=new Set<string>();
    const resolve=(span:Span)=>{
      keys(span,['pageIndex','startByte','endByte']);
      if(!span||![span.pageIndex,span.startByte,span.endByte].every(Number.isSafeInteger)||span.pageIndex<0||span.pageIndex>=source.length||span.startByte<0||span.endByte<=span.startByte||span.endByte>source[span.pageIndex].length)fail();
      return decoder.decode(source[span.pageIndex].subarray(span.startByte,span.endByte));
    };
    let pageOrder=0;
    for(const block of ir.blocks){
      keys(block,['blockId','kind','source','normalizedText','mapping']);
      if(typeof block.blockId!=='string'||ids.has(block.blockId)||!['paragraph','separator'].includes(block.kind)||typeof block.normalizedText!=='string'||!Array.isArray(block.mapping)||!block.mapping.length)fail();
      ids.add(block.blockId);resolve(block.source);
      const page=block.source.pageIndex;
      if(page<pageOrder||block.source.startByte!==ends[page])fail();
      pageOrder=page;
      let offset=block.source.startByte,normalizedOffset=0,text='';
      for(const map of block.mapping){
        keys(map,['normalizedStartByte','normalizedEndByte','source','operation']);
        const raw=resolve(map.source);
        if(map.source.pageIndex!==page||map.source.startByte!==offset||map.source.endByte>block.source.endByte||map.normalizedStartByte!==normalizedOffset)fail();
        if(!['IDENTITY','WHITESPACE'].includes(map.operation))fail();
        if(map.operation==='WHITESPACE'&&!/^[\s\u0085\u001c-\u001f]+$/u.test(raw))fail();
        const rendered=map.operation==='WHITESPACE'?' ':raw;
        text+=rendered;normalizedOffset+=Buffer.byteLength(rendered);offset=map.source.endByte;
        if(map.normalizedEndByte!==normalizedOffset)fail();
      }
      if(offset!==block.source.endByte||text!==block.normalizedText)fail();
      ends[page]=offset;
    }
    if(source.some((buffer,i)=>ends[i]!==buffer.length))fail();
  } catch {fail();}
}
