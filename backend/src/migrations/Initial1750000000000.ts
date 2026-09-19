import {MigrationInterface, QueryRunner} from 'typeorm';

/** Explicit versioned schema. Production never enables TypeORM synchronize. */
export class Initial1750000000000 implements MigrationInterface {
  async up(q:QueryRunner):Promise<void> {
    await q.query(`CREATE EXTENSION IF NOT EXISTS pgcrypto;
    CREATE TABLE documents (
      id uuid PRIMARY KEY DEFAULT gen_random_uuid(), title varchar NOT NULL,
      "documentType" varchar NOT NULL DEFAULT 'OTHER', "documentDate" date,
      "sourceType" varchar NOT NULL DEFAULT 'TEXT', "originalFilename" varchar,
      "storagePath" text, sha256 varchar, "mimeType" varchar, status varchar NOT NULL DEFAULT 'UPLOADED',
      summary text NOT NULL DEFAULT '', tags text[] NOT NULL DEFAULT '{}',
      "textVersion" integer NOT NULL DEFAULT 0, generation integer NOT NULL DEFAULT 1,
      "searchText" text NOT NULL DEFAULT '', "errorCode" varchar, "isSeed" boolean NOT NULL DEFAULT false,
      "createdAt" timestamptz NOT NULL DEFAULT now(), "updatedAt" timestamptz NOT NULL DEFAULT now(), "deletedAt" timestamptz);
    CREATE UNIQUE INDEX unique_active_document_hash ON documents(sha256) WHERE sha256 IS NOT NULL AND "deletedAt" IS NULL;
    CREATE INDEX document_fts ON documents USING GIN (to_tsvector('russian', "searchText"));
    CREATE INDEX document_tags ON documents USING GIN(tags);
    CREATE TABLE text_revisions (
      id uuid PRIMARY KEY DEFAULT gen_random_uuid(), "documentId" uuid NOT NULL REFERENCES documents(id),
      version integer NOT NULL, content text NOT NULL, pages jsonb NOT NULL DEFAULT '[]',
      parser varchar NOT NULL DEFAULT 'user-text', "parserVersion" varchar NOT NULL DEFAULT '1',
      "createdAt" timestamptz NOT NULL DEFAULT now(), UNIQUE("documentId",version));
    CREATE TABLE tags (id uuid PRIMARY KEY DEFAULT gen_random_uuid(), name varchar NOT NULL UNIQUE, "createdAt" timestamptz NOT NULL DEFAULT now());
    CREATE TABLE medical_facts (
      id uuid PRIMARY KEY DEFAULT gen_random_uuid(), "documentId" uuid NOT NULL REFERENCES documents(id),
      type varchar NOT NULL, name varchar NOT NULL, "valueText" text, "valueNumber" double precision, unit text, "eventDate" date,
      "assertionStatus" varchar NOT NULL DEFAULT 'UNKNOWN', "reviewStatus" varchar NOT NULL DEFAULT 'UNREVIEWED',
      "aiGenerated" boolean NOT NULL DEFAULT true, confidence double precision, "originalValue" jsonb NOT NULL,
      active boolean NOT NULL DEFAULT true, "createdAt" timestamptz NOT NULL DEFAULT now(), "updatedAt" timestamptz NOT NULL DEFAULT now());
    CREATE INDEX facts_document ON medical_facts("documentId");
    CREATE TABLE fact_provenance (
      id uuid PRIMARY KEY DEFAULT gen_random_uuid(), "factId" uuid NOT NULL UNIQUE REFERENCES medical_facts(id),
      "documentId" uuid NOT NULL REFERENCES documents(id), "textRevisionId" uuid NOT NULL REFERENCES text_revisions(id),
      "textVersion" integer NOT NULL, "pageNumber" integer, "sourceText" text NOT NULL, "createdAt" timestamptz NOT NULL DEFAULT now());
    CREATE TABLE fact_revisions (
      id uuid PRIMARY KEY DEFAULT gen_random_uuid(), "factId" uuid NOT NULL REFERENCES medical_facts(id),
      "oldValue" jsonb NOT NULL, "newValue" jsonb NOT NULL, "changeType" varchar NOT NULL, "createdAt" timestamptz NOT NULL DEFAULT now());
    CREATE INDEX revision_fact ON fact_revisions("factId");
    CREATE TABLE audit_events (
      id uuid PRIMARY KEY DEFAULT gen_random_uuid(), "entityType" varchar NOT NULL, "entityId" uuid NOT NULL,
      "documentId" uuid REFERENCES documents(id), action varchar NOT NULL, "payloadBefore" jsonb, "payloadAfter" jsonb, "createdAt" timestamptz NOT NULL DEFAULT now());
    CREATE INDEX audit_document ON audit_events("documentId");
    CREATE TABLE timeline_events (
      id uuid PRIMARY KEY DEFAULT gen_random_uuid(), "documentId" uuid NOT NULL REFERENCES documents(id),
      "factId" uuid REFERENCES medical_facts(id), "eventType" varchar NOT NULL, "eventDate" date,
      title varchar NOT NULL, description text NOT NULL, "createdAt" timestamptz NOT NULL DEFAULT now());
    CREATE INDEX timeline_document ON timeline_events("documentId");
    CREATE TABLE processing_jobs (
      id uuid PRIMARY KEY DEFAULT gen_random_uuid(), "documentId" uuid NOT NULL REFERENCES documents(id),
      operation varchar NOT NULL, status varchar NOT NULL DEFAULT 'QUEUED', attempt integer NOT NULL DEFAULT 0,
      generation integer NOT NULL, "errorCode" text, "availableAt" timestamptz,
      "createdAt" timestamptz NOT NULL DEFAULT now(), "updatedAt" timestamptz NOT NULL DEFAULT now());
    CREATE INDEX job_queue ON processing_jobs(status,"createdAt");
    CREATE TABLE extraction_runs (
      id uuid PRIMARY KEY DEFAULT gen_random_uuid(), "documentId" uuid NOT NULL REFERENCES documents(id),
      "textVersion" integer NOT NULL, model varchar, "modelDigest" varchar, "promptVersion" varchar,
      "schemaVersion" varchar, "parserVersion" varchar, status varchar NOT NULL, "rawJson" jsonb,
      "validationErrors" jsonb NOT NULL DEFAULT '[]', "completedAt" timestamptz,
      "createdAt" timestamptz NOT NULL DEFAULT now());
    CREATE TABLE consultations (
      id uuid PRIMARY KEY DEFAULT gen_random_uuid(), question text NOT NULL, content text NOT NULL,
      "contentHash" varchar NOT NULL, "reviewedHash" text, status varchar NOT NULL DEFAULT 'NEEDS_REVIEW',
      warnings jsonb NOT NULL DEFAULT '[]', "sourceRefs" jsonb NOT NULL DEFAULT '[]', contexts jsonb NOT NULL DEFAULT '[]',
      "generationVersion" varchar NOT NULL DEFAULT '1', "createdAt" timestamptz NOT NULL DEFAULT now(), "updatedAt" timestamptz NOT NULL DEFAULT now());`);
  }
  async down(q:QueryRunner):Promise<void> {
    await q.query('DROP TABLE consultations, extraction_runs, processing_jobs, timeline_events, audit_events, fact_revisions, fact_provenance, medical_facts, tags, text_revisions, documents');
  }
}
