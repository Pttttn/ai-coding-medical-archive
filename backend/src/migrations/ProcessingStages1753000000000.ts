import {MigrationInterface,QueryRunner} from 'typeorm';
// P1: the deterministic parse stage is stored before any model call and reused by retries of the same job;
// every extraction run records the full recipe hash and the exact source IR it was extracted from.
export class ProcessingStages1753000000000 implements MigrationInterface {
  async up(q:QueryRunner):Promise<void>{await q.query(`
    ALTER TABLE source_ir_revisions ADD COLUMN "parseRecipe" jsonb, ADD COLUMN "parseRecipeHash" varchar(64);
    ALTER TABLE processing_jobs ADD COLUMN "sourceIrRevisionId" uuid REFERENCES source_ir_revisions(id);
    ALTER TABLE extraction_runs ADD COLUMN "sourceIrRevisionId" uuid REFERENCES source_ir_revisions(id), ADD COLUMN "recipeHash" varchar(64);
    CREATE INDEX extraction_run_source_ir ON extraction_runs("sourceIrRevisionId");
  `);}
  async down(q:QueryRunner):Promise<void>{await q.query(`
    DROP INDEX extraction_run_source_ir;
    ALTER TABLE extraction_runs DROP COLUMN "recipeHash", DROP COLUMN "sourceIrRevisionId";
    ALTER TABLE processing_jobs DROP COLUMN "sourceIrRevisionId";
    ALTER TABLE source_ir_revisions DROP COLUMN "parseRecipeHash", DROP COLUMN "parseRecipe";
  `);}
}
