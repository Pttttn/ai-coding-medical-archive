import {MigrationInterface,QueryRunner} from 'typeorm';
export class ConsultationHistory1752000000000 implements MigrationInterface {
  async up(q:QueryRunner):Promise<void>{await q.query(`
    CREATE TABLE consultation_prompts (
      id uuid PRIMARY KEY DEFAULT gen_random_uuid(), "consultationId" uuid NOT NULL REFERENCES consultations(id),
      content text NOT NULL, "contentHash" varchar(64) NOT NULL, "sourceRefs" jsonb NOT NULL,
      "createdAt" timestamptz NOT NULL DEFAULT now(), UNIQUE("consultationId","contentHash"), UNIQUE(id,"consultationId")
    );
    CREATE TABLE consultation_responses (
      id uuid PRIMARY KEY, "consultationId" uuid NOT NULL REFERENCES consultations(id), "promptId" uuid NOT NULL,
      model text NOT NULL CHECK(length(trim(model)) BETWEEN 1 AND 200),
      content text NOT NULL CHECK(length(trim(content)) BETWEEN 1 AND 100000),
      "createdAt" timestamptz NOT NULL DEFAULT now(),
      FOREIGN KEY("promptId","consultationId") REFERENCES consultation_prompts(id,"consultationId")
    );
    CREATE INDEX consultation_responses_parent ON consultation_responses("consultationId","createdAt");
    CREATE INDEX consultations_recent ON consultations("createdAt" DESC,id DESC);
    INSERT INTO consultation_prompts("consultationId",content,"contentHash","sourceRefs")
      SELECT id,content,"contentHash","sourceRefs" FROM consultations WHERE "reviewedHash"="contentHash";
    CREATE FUNCTION reject_consultation_history_update() RETURNS trigger LANGUAGE plpgsql AS $$
      BEGIN RAISE EXCEPTION 'Consultation history is immutable'; END $$;
    CREATE TRIGGER immutable_consultation_prompts BEFORE UPDATE ON consultation_prompts
      FOR EACH ROW EXECUTE FUNCTION reject_consultation_history_update();
    CREATE TRIGGER immutable_consultation_responses BEFORE UPDATE ON consultation_responses
      FOR EACH ROW EXECUTE FUNCTION reject_consultation_history_update();
  `);}
  async down(q:QueryRunner):Promise<void>{await q.query('DROP TABLE consultation_responses, consultation_prompts; DROP FUNCTION reject_consultation_history_update(); DROP INDEX consultations_recent');}
}
