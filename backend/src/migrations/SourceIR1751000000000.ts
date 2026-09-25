import {MigrationInterface,QueryRunner} from 'typeorm';
export class SourceIR1751000000000 implements MigrationInterface {
  async up(q:QueryRunner):Promise<void>{await q.query(`
    CREATE TABLE source_ir_revisions (
      id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
      "documentId" uuid NOT NULL REFERENCES documents(id),
      "textRevisionId" uuid NOT NULL REFERENCES text_revisions(id),
      "irHash" varchar(64) NOT NULL,
      "schemaVersion" varchar NOT NULL,
      content jsonb NOT NULL,
      "createdAt" timestamptz NOT NULL DEFAULT now(),
      UNIQUE("textRevisionId","irHash")
    );
    CREATE INDEX source_ir_document ON source_ir_revisions("documentId");
    CREATE FUNCTION prevent_source_ir_update() RETURNS trigger LANGUAGE plpgsql AS $$
      BEGIN RAISE EXCEPTION 'Source IR revisions are immutable'; END;
    $$;
    CREATE TRIGGER source_ir_immutable BEFORE UPDATE ON source_ir_revisions FOR EACH ROW EXECUTE FUNCTION prevent_source_ir_update();
  `);}
  async down(q:QueryRunner):Promise<void>{await q.query('DROP TABLE source_ir_revisions; DROP FUNCTION prevent_source_ir_update();');}
}
