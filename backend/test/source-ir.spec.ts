import {readFileSync} from 'node:fs';
import {join} from 'node:path';
import {irHash,validateSourceIR,SourceIR} from '../src/source-ir';
const fixture=():SourceIR=>JSON.parse(readFileSync(join(__dirname,'../../contracts/source-ir-v1.synthetic.json'),'utf8'));
test('accepts Python-generated Unicode mapping and canonical digest',()=>{const ir=fixture();expect(()=>validateSourceIR(ir,ir.documentId,ir.pages)).not.toThrow();});
test.each(['normalized','boundary','omission','document'])('rejects tampered %s even with recalculated digest',kind=>{
  const ir=fixture();
  if(kind==='normalized')ir.blocks[0].normalizedText='1,4';
  if(kind==='boundary')ir.blocks[0].mapping[0].source.endByte=1;
  if(kind==='omission')ir.blocks.pop();
  if(kind==='document')ir.documentId='another-document';
  const {irHash:previous,...body}=ir;void previous;ir.irHash=irHash(body);
  expect(()=>validateSourceIR(ir,'synthetic-cross-language',fixture().pages)).toThrow();
});
