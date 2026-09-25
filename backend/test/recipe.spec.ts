import {readFileSync} from 'node:fs';
import {join} from 'node:path';
import {irHash,SourceIR} from '../src/source-ir';
import {validateParseRecipe,validateProcessingRecipe} from '../src/recipe';
const read=(name:string)=>JSON.parse(readFileSync(join(__dirname,'../../contracts',name),'utf8'));
const fixture=()=>read('processing-recipe-v1.synthetic.json');
const ir=():SourceIR=>read('source-ir-v1.synthetic.json');
const rehash=({recipeHash,...body}:any)=>{void recipeHash;return {...body,recipeHash:irHash(body)};};
test('accepts Python-generated parse and processing recipes with the same canonical hash',()=>{
  const f=fixture();
  expect(()=>validateParseRecipe(f.parseRecipe,ir())).not.toThrow();
  expect(validateProcessingRecipe(f.processingRecipe,f.parseRecipe.recipeHash)).toBe(f.processingRecipe.recipeHash);
});
test.each([
  ['changed model without new hash',(f:any)=>{f.processingRecipe.model='other';}],
  ['changed nested decoding option without new hash',(f:any)=>{f.processingRecipe.generationOptions.seed=7;}],
  ['recipe of another parse stage',(f:any)=>{f.processingRecipe=rehash({...f.processingRecipe,parse:rehash({...f.parseRecipe,parserVersion:'other'})});}],
  ['unknown recipe version',(f:any)=>{f.processingRecipe=rehash({...f.processingRecipe,recipeVersion:'processing-recipe-v0'});}],
])('rejects processing recipe: %s',(_name,tamper)=>{
  const f=fixture();tamper(f);
  expect(()=>validateProcessingRecipe(f.processingRecipe,f.parseRecipe.recipeHash)).toThrow();
});
test.each([
  ['parser of another IR',(r:any)=>rehash({...r,parserVersion:'other'})],
  ['extra field',(r:any)=>rehash({...r,chunker:'x'})],
  ['wrong hash',(r:any)=>({...r,recipeHash:'0'.repeat(64)})],
])('rejects parse recipe: %s',(_name,tamper)=>{
  expect(()=>validateParseRecipe(tamper(fixture().parseRecipe),ir())).toThrow();
});
