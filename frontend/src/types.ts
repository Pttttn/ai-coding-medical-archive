export interface Page<T> { items: T[]; page: number; pageSize: number; total: number }
export interface Document {
  id: string; title: string; documentType: string; documentDate: string | null;
  sourceType: string; status: string; summary: string | null; tags: string[];
  createdAt: string; updatedAt: string; deletedAt: string | null;
  visit?: Visit | null; laboratory?: Laboratory | null; pages?: { pageNumber: number | null; text: string }[];
  text?: string; textVersion?: number; originalFilename?: string; facts?: Fact[];
  textRevisions?: TextRevision[]; latestJob?: { id: string; status: string; error?: string; errorCode?: string; attempts?: number }; processingError?: string; processingWarnings?: string[]; isSeed?: boolean;
  processingRevision?: { active: ProcessingRevisionView | null; prepared: ProcessingRevisionView | null };
  /** Reprocess modes the document supports; the text version the visible facts were extracted from. */
  reprocessModes?: ReprocessMode[]; factsTextVersion?: number | null;
}
export type ReprocessMode = 'CURRENT_TEXT' | 'ORIGINAL';
export interface ProcessingRevisionView { id: string; status: string; recipeHash: string; textRevisionId: string; textVersion?: number | null; createdAt: string; activatedAt: string | null; indexedChunks: number | null }
export interface TextRevision { id: string; version: number; text?: string; content?: string; createdAt: string; parser?: string }
export interface Fact {
  id: string; documentId: string; type: string; name: string; valueText: string | null;
  valueNumber: number | null; unit: string | null; eventDate: string | null;
  assertionStatus: string; reviewStatus: string; confidence: number | null;
  provenance?: Provenance | Provenance[]; createdAt?: string; updatedAt?: string; originalValue?: Record<string, unknown>;
}
export interface Provenance { documentId?: string; page?: number; pageNumber?: number; sourceText: string; textVersion?: number; version?: number; position?: number }
export interface FactSource { factId: string; documentId: string; textVersion: number; pageNumber: number | null; sourceText: string; documentTitle: string; textRevisionId: string }
export interface FactRevision { id: string; factId: string; oldValue: unknown; newValue: unknown; changeType: string; createdAt: string }
export interface HistoryEvent { id: string; action: string; entityType: string; entityId: string; documentId?: string; createdAt: string; payloadBefore?: unknown; payloadAfter?: unknown; before?: unknown; after?: unknown }
export interface TimelineEvent { id: string; documentId: string; eventType: string; eventDate: string | null; title: string; description: string; category?: string; documentTitle?: string; earlierText?: boolean }
export interface AskSource { documentDate?: string | null; documentId?: string; source: string; chunkId: string; position: number; pageNumber?: number; text?: string }
export interface AskAnswer { answer: string; sources: AskSource[]; insufficientContext?: boolean; trace?: unknown; reasonCode?: string; warnings?: string[]; coverage?: { eligibleDocuments: number; scannedDocuments: number; complete: boolean; period: { from: string | null; to: string | null; asOf: string } } }
export interface Consultation { prompts?: ConsultationPrompt[]; responses?: ConsultationResponse[]; id: string; question: string; content: string; contentHash: string; reviewedHash?: string | null; status: string; warnings: string[]; sourceRefs: {documentId: string; title: string; textVersion: number}[]; contexts?: { text: string }[]; createdAt: string }
export interface DashboardData {
  totalDocuments: number; processedDocuments: number; failedDocuments: number; pendingDocuments: number;
  medicalFacts: number; timelineEvents: number;
  documentsByType: { type: string; count: number }[];
  documentsOverTime: { month: string; count: number }[];
  recentDocuments: Document[]; recentChanges: HistoryEvent[];
}





export interface Laboratory {
  rows: { name: string; result: { raw: string }; unit: string | null; referenceRaw: string | null; subject: string;
    sourceText: string; source: { pageIndex: number } }[];
  dates: { role: string; raw: string }[];
  issues: { code: string }[];
  candidateRows: number;
}

export interface Visit {
  verifications?: { statementIndex: number; status: string; reason: string; alternative: { subject: string; kind: string; assertion: string; medicationState: string; temporality: string; sourceText: string } | null }[];
  candidateBlocks: number; processedBlocks: string[]; issues: { code: string }[];
  statements: { name: string; kind: string; subject: string; assertion: string; medicationState: string;
    temporality: string; sourceText: string; contextText: string; source: { pageIndex: number } }[];
}

export interface ConsultationSummary { id:string; question:string; status:string; createdAt:string; updatedAt:string; sourceCount:number; responseCount:number }
export interface ConsultationPrompt { id:string; content:string; contentHash:string; createdAt:string }
export interface ConsultationResponse { id:string; promptId:string; model:string; content:string; createdAt:string }
