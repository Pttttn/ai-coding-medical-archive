import {MigrationInterface,QueryRunner} from 'typeorm';
// P3: a reprocess names its parse source: the current text (stored parse stage reused) or the original file.
// NULL keeps the automatic choice of earlier jobs.
export class ReprocessModes1755000000000 implements MigrationInterface {
  async up(q:QueryRunner):Promise<void>{await q.query(`
    ALTER TABLE processing_jobs ADD COLUMN "parseSource" varchar CHECK ("parseSource" IN ('CURRENT_TEXT','ORIGINAL'));
  `);}
  async down(q:QueryRunner):Promise<void>{await q.query(`ALTER TABLE processing_jobs DROP COLUMN "parseSource";`);}
}
