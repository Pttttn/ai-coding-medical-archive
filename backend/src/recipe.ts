import {AiError} from './core';
import {irHash,SourceIR} from './source-ir';

export const RECIPE_VERSION='processing-recipe-v1';
export type ParseRecipe={recipeVersion:typeof RECIPE_VERSION;stage:'SOURCE_ONLY';parserVersion:string;sourceIRVersion:string;normalizerVersion:string;recipeHash:string};
const isObject=(v:unknown):v is Record<string,unknown>=>!!v&&typeof v==='object'&&!Array.isArray(v);
/** Recomputes the recipe hash with the same canonical JSON as source IR; Python and TypeScript must agree. */
function hashed(recipe:unknown):recipe is Record<string,unknown>&{recipeHash:string} {
  if(!isObject(recipe))return false;
  const {recipeHash,...body}=recipe;
  try {return typeof recipeHash==='string'&&/^[0-9a-f]{64}$/.test(recipeHash)&&body.recipeVersion===RECIPE_VERSION&&irHash(body)===recipeHash;}
  catch {return false;}
}
export function validateParseRecipe(recipe:unknown,ir:SourceIR):asserts recipe is ParseRecipe {
  if(!hashed(recipe)||Object.keys(recipe).sort().join(',')!=='normalizerVersion,parserVersion,recipeHash,recipeVersion,sourceIRVersion,stage'
    ||recipe.stage!=='SOURCE_ONLY'||recipe.parserVersion!==ir.parserVersion||recipe.sourceIRVersion!==ir.schemaVersion||recipe.normalizerVersion!==ir.normalizerVersion)
    throw new AiError('RECIPE_INVALID');
}
/** The extraction recipe must name the stored parse stage it was built on. */
export function validateProcessingRecipe(recipe:unknown,parseRecipeHash:string):string {
  if(!hashed(recipe)||!hashed(recipe.parse)||recipe.parse.recipeHash!==parseRecipeHash||!isObject(recipe.annotation)||!isObject(recipe.index)||typeof recipe.method!=='string')
    throw new AiError('RECIPE_INVALID');
  return recipe.recipeHash;
}
/** Index settings the extraction recipe named for its revision; runs without a recipe (legacy) have none. */
export function expectedIndexSettings(rawJson:unknown):Record<string,unknown>|null {
  const index=isObject(rawJson)&&isObject(rawJson.processingRecipe)?rawJson.processingRecipe.index:null;
  return isObject(index)?index:null;
}
/** The indexer's report of the settings it used must equal the recipe's, whatever the key order. */
export function confirmIndexSettings(expected:Record<string,unknown>,used:unknown):void {
  let same=false;
  try {same=isObject(used)&&irHash(used)===irHash(expected);}catch {same=false;}
  if(!same)throw new AiError('INDEX_RECIPE_MISMATCH');
}
