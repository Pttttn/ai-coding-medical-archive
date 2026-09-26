import {MigrationInterface,QueryRunner} from 'typeorm';
// P3: facts and search chunks of one extraction become visible together. A processing revision is prepared
// (inactive facts, staged index) and then activated in one short transaction; the previous one stays readable until then.
export class ProcessingRevisions1754000000000 implements MigrationInterface {
  async up(q:QueryRunner):Promise<void>{await q.query(`
    CREATE TABLE processing_revisions (
      id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
      "documentId" uuid NOT NULL REFERENCES documents(id),
      "sourceIrRevisionId" uuid NOT NULL REFERENCES source_ir_revisions(id),
      "textRevisionId" uuid NOT NULL REFERENCES text_revisions(id),
      "extractionRunId" uuid NOT NULL UNIQUE REFERENCES extraction_runs(id),
      "recipeHash" varchar(64) NOT NULL,
      status varchar NOT NULL DEFAULT 'PREPARED' CHECK (status IN ('PREPARED','ACTIVE','SUPERSEDED','FAILED')),
      "indexManifest" jsonb,
      "createdAt" timestamptz NOT NULL DEFAULT now(),
      "activatedAt" timestamptz
    );
    CREATE INDEX processing_revision_document ON processing_revisions("documentId");
    CREATE UNIQUE INDEX processing_revision_one_active ON processing_revisions("documentId") WHERE status='ACTIVE';
    CREATE FUNCTION prevent_processing_revision_rebind() RETURNS trigger LANGUAGE plpgsql AS $$
      BEGIN
        IF (NEW."documentId",NEW."sourceIrRevisionId",NEW."textRevisionId",NEW."extractionRunId",NEW."recipeHash")
           IS DISTINCT FROM (OLD."documentId",OLD."sourceIrRevisionId",OLD."textRevisionId",OLD."extractionRunId",OLD."recipeHash")
        THEN RAISE EXCEPTION 'Processing revision identity is immutable'; END IF;
        RETURN NEW;
      END;
    $$;
    CREATE TRIGGER processing_revision_immutable BEFORE UPDATE ON processing_revisions FOR EACH ROW EXECUTE FUNCTION prevent_processing_revision_rebind();
    ALTER TABLE documents ADD COLUMN "activeProcessingRevisionId" uuid REFERENCES processing_revisions(id);
    ALTER TABLE medical_facts ADD COLUMN "processingRevisionId" uuid REFERENCES processing_revisions(id);
    CREATE INDEX medical_fact_processing_revision ON medical_facts("processingRevisionId");
    ALTER TABLE processing_jobs ADD COLUMN "processingRevisionId" uuid REFERENCES processing_revisions(id);
  `);}
  async down(q:QueryRunner):Promise<void>{await q.query(`
    ALTER TABLE processing_jobs DROP COLUMN "processingRevisionId";
    DROP INDEX medical_fact_processing_revision;
    ALTER TABLE medical_facts DROP COLUMN "processingRevisionId";
    ALTER TABLE documents DROP COLUMN "activeProcessingRevisionId";
    DROP TABLE processing_revisions;
    DROP FUNCTION prevent_processing_revision_rebind();
  `);}
}
